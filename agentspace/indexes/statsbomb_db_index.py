"""
Build a comprehensive, hierarchical StatsBomb database index for fast local lookups.

Outputs JSON files under `.cache/db_index/`:
- competitions_index.json
- seasons_index.json
- teams_index.json
- players_index.json
- managers_index.json
- matches_index.json
- relationship_graph.json
- stats_summary.json
- validation_report.json
- quick_lookup_guide.md

This module avoids tool calls at runtime by precomputing indices from the
StatsBomb API via `StatsBombClient`, then reading from JSON thereafter.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from ..clients.statsbomb import StatsBombClient


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _canonical(text: str) -> str:
    # Lower, strip, collapse, remove punctuation/diacritics
    s = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _key_variants(name: str) -> List[str]:
    # Variants for by_name indexing: original, lowercase, canonical, spaces removed
    if not name:
        return []
    variants = {name, name.lower(), _canonical(name)}
    variants.add("".join(name.lower().split()))
    return [v for v in variants if v]


@dataclass
class IndexPaths:
    base_dir: Path = Path(".cache/db_index")
    competitions: Path = field(init=False)
    seasons: Path = field(init=False)
    teams: Path = field(init=False)
    players: Path = field(init=False)
    managers: Path = field(init=False)
    matches: Path = field(init=False)
    relationships: Path = field(init=False)
    stats: Path = field(init=False)
    validation: Path = field(init=False)
    guide: Path = field(init=False)

    def __post_init__(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.competitions = self.base_dir / "competitions_index.json"
        self.seasons = self.base_dir / "seasons_index.json"
        self.teams = self.base_dir / "teams_index.json"
        self.players = self.base_dir / "players_index.json"
        self.managers = self.base_dir / "managers_index.json"
        self.matches = self.base_dir / "matches_index.json"
        self.relationships = self.base_dir / "relationship_graph.json"
        self.stats = self.base_dir / "stats_summary.json"
        self.validation = self.base_dir / "validation_report.json"
        self.guide = self.base_dir / "quick_lookup_guide.md"


@dataclass
class IndexBuildConfig:
    competitions: Optional[Iterable[int]] = None  # None → all competitions
    include_player_stats: bool = True  # use player-season stats to enrich attributes
    include_lineups: bool = True  # fetch lineups to map players/jerseys/managers
    include_player_mapping: bool = True  # use player-mapping API as fallback/enrichment
    write_intermediate: bool = False  # optionally dump per-comp/season partials
    paths: IndexPaths = field(default_factory=IndexPaths)


class StatsBombDBIndexer:
    def __init__(self, config: Optional[IndexBuildConfig] = None) -> None:
        self.cfg = config or IndexBuildConfig()
        self.client = StatsBombClient()
        # Stores
        self.competitions: Dict[int, Dict[str, Any]] = {}
        self.seasons: Dict[int, Dict[str, Any]] = {}
        self.teams: Dict[int, Dict[str, Any]] = {}
        self.players: Dict[int, Dict[str, Any]] = {}
        self.managers: Dict[int, Dict[str, Any]] = {}
        self.matches: Dict[int, Dict[str, Any]] = {}

        # Reverse/relationship maps
        self.comp_to_seasons: Dict[int, Set[int]] = defaultdict(set)
        self.season_to_teams: Dict[int, Set[int]] = defaultdict(set)
        self.season_to_players: Dict[int, Set[int]] = defaultdict(set)
        self.season_to_matches: Dict[int, Set[int]] = defaultdict(set)
        self.team_to_seasons: Dict[int, Set[int]] = defaultdict(set)
        self.team_to_players: Dict[int, Set[int]] = defaultdict(set)
        self.player_to_teams: Dict[int, Set[int]] = defaultdict(set)
        self.player_to_seasons: Dict[int, Set[int]] = defaultdict(set)
        self.player_to_matches: Dict[int, Set[int]] = defaultdict(set)
        self.match_to_players: Dict[int, Set[int]] = defaultdict(set)

        # Name indices (with fuzzy variants)
        self.competition_name_index: Dict[str, int] = {}
        self.competition_by_country: Dict[str, List[int]] = defaultdict(list)
        self.competition_by_type: Dict[str, List[int]] = defaultdict(list)

        self.season_by_year: Dict[str, List[int]] = defaultdict(list)
        self.season_by_competition: Dict[int, List[int]] = defaultdict(list)

        self.team_name_index: Dict[str, int] = {}
        self.team_by_country: Dict[str, List[int]] = defaultdict(list)
        self.team_by_season: Dict[int, List[int]] = defaultdict(list)

        self.player_name_index: Dict[str, int] = {}
        self.player_by_country: Dict[str, List[int]] = defaultdict(list)
        self.player_by_season: Dict[int, List[int]] = defaultdict(list)
        self.player_by_position: Dict[str, List[int]] = defaultdict(list)
        self.player_by_team: Dict[int, List[int]] = defaultdict(list)

        self.manager_name_index: Dict[str, int] = {}
        self.manager_by_team: Dict[int, List[int]] = defaultdict(list)
        self.manager_by_season: Dict[int, List[int]] = defaultdict(list)

        self.validation_issues: List[str] = []

    # -------------------- Fetch and aggregate --------------------
    def build(self) -> None:
        comps = self._fetch_competitions()
        for comp in comps:
            comp_id = comp.get("competition_id")
            if not isinstance(comp_id, int):
                continue
            if self.cfg.competitions and comp_id not in set(self.cfg.competitions):
                continue
            self._ingest_competition(comp)
            seasons = []
            try:
                seasons = self.client.list_seasons(comp_id) or []
            except Exception as exc:  # pragma: no cover - tolerate missing endpoints
                self.validation_issues.append(
                    f"list_seasons failed for competition {comp_id}: {exc}"
                )
            # Fallback: derive seasons from player-mapping when list_seasons fails/empty
            if (not seasons) and self.cfg.include_player_mapping:
                mapping = self.client.get_player_mapping(
                    competition_id=comp_id,
                    all_account_data=True,
                    add_matches_played=False,
                )
                # Build a set of seasons from mapping
                seen = {}
                for row in mapping:
                    sid = row.get("season_id")
                    sname = row.get("season_name")
                    if isinstance(sid, int) and sid not in seen:
                        seen[sid] = {"season_id": sid, "season_name": sname}
                seasons = list(seen.values())
            for season in seasons:
                season_id = season.get("season_id")
                if not isinstance(season_id, int):
                    continue
                self._ingest_season(season, comp)
                matches = []
                try:
                    matches = self.client.list_matches(comp_id, season_id) or []
                except Exception as exc:  # pragma: no cover - tolerate gaps
                    self.validation_issues.append(
                        f"list_matches failed for competition {comp_id} season {season_id}: {exc}"
                    )
                for match in matches:
                    self._ingest_match(match, comp, season)

                # after matches fetched, build season aggregates
                self._finalize_season(comp_id, season_id)

                if self.cfg.include_player_stats:
                    self._enrich_players_from_season_stats(comp_id, season_id)
                # Fallback/enrichment via player-mapping API
                if self.cfg.include_player_mapping:
                    self._enrich_from_player_mapping(comp_id, season_id)

        # Finalize indices and persist
        self._finalize_and_write()

    def _fetch_competitions(self) -> List[Dict[str, Any]]:
        try:
            return list(self.client.list_competitions())
        except Exception:  # pragma: no cover - network issues fallback to empty
            return []

    # -------------------- Ingestors --------------------
    def _ingest_competition(self, comp: Dict[str, Any]) -> None:
        comp_id = int(comp.get("competition_id"))
        name = str(comp.get("competition_name", ""))
        country = str(comp.get("country_name", "")) if comp.get("country_name") else ""
        ctype = str(comp.get("competition_format", "")) or str(comp.get("competition_type", ""))

        node = self.competitions.setdefault(comp_id, {
            "id": comp_id,
            "name": name,
            "country": country or None,
            "type": (ctype or None),
            "seasons": [],
            "date_range": {"start": None, "end": None},
        })
        # index name variants
        for key in _key_variants(name):
            self.competition_name_index.setdefault(key, comp_id)
        if country:
            self.competition_by_country[country].append(comp_id)
        if ctype:
            self.competition_by_type[ctype].append(comp_id)

    def _ingest_season(self, season: Dict[str, Any], comp: Dict[str, Any]) -> None:
        comp_id = int(comp.get("competition_id"))
        comp_name = str(comp.get("competition_name", ""))
        season_id = int(season.get("season_id"))
        season_name = str(season.get("season_name", ""))

        node = self.seasons.setdefault(season_id, {
            "id": season_id,
            "name": season_name or None,
            "competition_id": comp_id,
            "competition_name": comp_name or None,
            "teams": set(),  # temp set → list later
            "match_ids": [],
            "date_range": {"start": None, "end": None},
            "match_count": 0,
        })

        self.comp_to_seasons[comp_id].add(season_id)
        if season_name:
            self.season_by_year[season_name].append(season_id)
        self.season_by_competition[comp_id].append(season_id)

    def _ingest_match(self, match: Dict[str, Any], comp: Dict[str, Any], season: Dict[str, Any]) -> None:
        comp_id = int(comp.get("competition_id"))
        season_id = int(season.get("season_id"))
        match_id = int(match.get("match_id"))

        # Extract date/week fields if available
        match_date = match.get("match_date") or match.get("match_date_time") or match.get("match_date_utc")
        if isinstance(match_date, str) and len(match_date) > 10:
            match_date = match_date[:10]
        match_week = match.get("match_week") or match.get("match_round")

        home_team = match.get("home_team") or {}
        away_team = match.get("away_team") or {}
        home_id = home_team.get("home_team_id") or home_team.get("team_id")
        away_id = away_team.get("away_team_id") or away_team.get("team_id")
        home_name = home_team.get("home_team_name") or home_team.get("team_name") or ""
        away_name = away_team.get("away_team_name") or away_team.get("team_name") or ""
        home_country = home_team.get("country") or home_team.get("country_name") or None
        away_country = away_team.get("country") or away_team.get("country_name") or None

        if isinstance(home_id, int):
            self._ensure_team(home_id, home_name, home_country)
            self.season_to_teams[season_id].add(home_id)
            self.team_to_seasons[home_id].add(season_id)
        if isinstance(away_id, int):
            self._ensure_team(away_id, away_name, away_country)
            self.season_to_teams[season_id].add(away_id)
            self.team_to_seasons[away_id].add(season_id)

        # Create match summary
        self.matches[match_id] = {
            "id": match_id,
            "season_id": season_id,
            "competition_id": comp_id,
            "home_team_id": int(home_id) if isinstance(home_id, int) else None,
            "away_team_id": int(away_id) if isinstance(away_id, int) else None,
            "match_date": match_date,
            "match_week": int(match_week) if isinstance(match_week, int) else None,
        }

        # Season aggregates
        self.seasons[season_id]["match_ids"].append(match_id)
        self.seasons[season_id]["match_count"] += 1
        self.season_to_matches[season_id].add(match_id)
        self.competitions[int(comp_id)]["seasons"] = sorted(self.comp_to_seasons[comp_id])

        # Update date ranges
        self._update_date_range(self.seasons[season_id]["date_range"], match_date)
        self._update_date_range(self.competitions[comp_id]["date_range"], match_date)

        # Managers if present
        for side in ("home_managers", "away_managers"):
            mgrs = match.get(side) or []
            for mgr in mgrs if isinstance(mgrs, list) else []:
                mgr_id = mgr.get("id") or mgr.get("manager_id")
                name = mgr.get("name") or mgr.get("manager_name")
                if isinstance(mgr_id, int) and name:
                    self._ensure_manager(mgr_id, name)
                    team_id = home_id if side == "home_managers" else away_id
                    if isinstance(team_id, int):
                        self.manager_by_team[team_id].append(mgr_id)
                        self.manager_by_season[season_id].append(mgr_id)
                        self.managers[mgr_id].setdefault("teams", set()).add(int(team_id))
                        self.managers[mgr_id].setdefault("seasons", set()).add(season_id)

        # Lineups for players/jersey numbers if configured
        if self.cfg.include_lineups:
            try:
                lineups = self.client.get_lineups(match_id) or []
            except Exception:
                lineups = []
            for team_block in lineups:
                t_id = team_block.get("team_id")
                t_name = team_block.get("team_name")
                if isinstance(t_id, int):
                    self._ensure_team(t_id, t_name or "", None)
                for player in team_block.get("lineup", []) or []:
                    pid = player.get("player_id")
                    pname = player.get("player_name")
                    if not (isinstance(pid, int) and pname):
                        continue
                    country = player.get("country", {}).get("name") if isinstance(player.get("country"), dict) else None
                    pos = player.get("position", {}).get("name") if isinstance(player.get("position"), dict) else None
                    jersey_no = player.get("jersey_number")
                    self._ensure_player(pid, pname, country)
                    if pos:
                        self.players[pid].setdefault("positions", set()).add(pos)
                        self.player_by_position[pos].append(pid)
                    if isinstance(t_id, int):
                        self.players[pid].setdefault("teams", set()).add(t_id)
                        self.player_by_team[t_id].append(pid)
                        # jersey map by team and season
                        jerseys = self.players[pid].setdefault("jersey_numbers", {})
                        team_entry = jerseys.setdefault(str(t_id), {})
                        if isinstance(season_id, int) and isinstance(jersey_no, int):
                            team_entry[str(season_id)] = jersey_no
                    # relationship graphs
                    self.player_to_seasons[pid].add(season_id)
                    self.player_to_matches[pid].add(match_id)
                    if isinstance(t_id, int):
                        self.player_to_teams[pid].add(t_id)
                        self.team_to_players[t_id].add(pid)
                    self.match_to_players[match_id].add(pid)
                    self.season_to_players[season_id].add(pid)

    def _enrich_players_from_season_stats(self, competition_id: int, season_id: int) -> None:
        try:
            rows = self.client.get_player_season_stats(competition_id, season_id) or []
        except Exception:
            rows = []
        for row in rows:
            pid = row.get("player_id")
            pname = row.get("player_name")
            if not (isinstance(pid, int) and pname):
                continue
            team_id = row.get("team_id")
            nationality = row.get("nationality_name") or row.get("country_name") or None
            pos = row.get("position") or row.get("position_name") or None
            self._ensure_player(pid, pname, nationality)
            if pos:
                self.players[pid].setdefault("positions", set()).add(str(pos))
                self.player_by_position[str(pos)].append(pid)
            if isinstance(team_id, int):
                self.players[pid].setdefault("teams", set()).add(team_id)
                self.player_by_team[team_id].append(pid)
            self.players[pid].setdefault("seasons", set()).add(season_id)
            self.player_by_season[season_id].append(pid)

    def _enrich_from_player_mapping(self, competition_id: int, season_id: int) -> None:
        mapping = self.client.get_player_mapping(
            competition_id=competition_id,
            season_id=season_id,
            add_matches_played=True,
        )
        for row in mapping:
            pid = row.get("offline_player_id")
            pname = row.get("player_name")
            if not (isinstance(pid, int) and pname):
                continue
            team_id = row.get("offline_team_id")
            team_name = row.get("team_name") or ""
            self._ensure_player(pid, pname, row.get("country_of_birth_name"))
            # enrich player attrs
            bdate = row.get("player_birth_date")
            if bdate:
                self.players[pid]["birth_date"] = bdate
            height = row.get("player_height")
            if height is not None:
                self.players[pid]["height_cm"] = height
            weight = row.get("player_weight")
            if weight is not None:
                self.players[pid]["weight_kg"] = weight
            foot = row.get("player_preferred_foot") or row.get("player_perferred_foot")
            if foot:
                self.players[pid]["preferred_foot"] = foot

            # ensure team/season links
            if isinstance(team_id, int):
                self._ensure_team(team_id, team_name, None)
                self.season_to_teams[season_id].add(team_id)
                self.team_to_seasons[team_id].add(season_id)
                self.players[pid].setdefault("teams", set()).add(team_id)
                self.team_to_players[team_id].add(pid)
                self.player_by_team[team_id].append(pid)
            self.player_to_seasons[pid].add(season_id)
            self.player_by_season[season_id].append(pid)
            self.season_to_players[season_id].add(pid)

            # dates from earliest/most_recent
            rng = self.players[pid].setdefault("date_range", {"first": None, "last": None})
            if row.get("earliest_match_date"):
                rng["first"] = min(filter(None, [rng.get("first"), row.get("earliest_match_date")])) if rng.get("first") else row.get("earliest_match_date")
            if row.get("most_recent_match_date"):
                rng["last"] = max(filter(None, [rng.get("last"), row.get("most_recent_match_date")])) if rng.get("last") else row.get("most_recent_match_date")

            # matches played list
            matches = row.get("matches_played") or []
            for m in matches if isinstance(matches, list) else []:
                mid = m.get("offline_match_id") or m.get("match_id")
                mdate = m.get("match_date")
                if isinstance(mid, int):
                    # ensure minimal match record
                    self.matches.setdefault(mid, {
                        "id": mid,
                        "season_id": season_id,
                        "competition_id": competition_id,
                        "home_team_id": None,
                        "away_team_id": None,
                        "match_date": mdate,
                        "match_week": None,
                    })
                    self.player_to_matches[pid].add(mid)
                    self.match_to_players[mid].add(pid)
                    self.season_to_matches[season_id].add(mid)

    # -------------------- Helpers --------------------
    def _ensure_team(self, team_id: int, name: str, country: Optional[str]) -> None:
        node = self.teams.setdefault(team_id, {
            "id": team_id,
            "name": name or None,
            "country": country or None,
            "seasons": set(),
            "competitions": set(),
            "managers": set(),
            "players": set(),
            "match_count": 0,
        })
        if name:
            for key in _key_variants(name):
                self.team_name_index.setdefault(key, team_id)
        if country:
            self.team_by_country[country].append(team_id)

    def _ensure_player(self, player_id: int, name: str, country: Optional[str]) -> None:
        node = self.players.setdefault(player_id, {
            "id": player_id,
            "name": name or None,
            "common_name": None,
            "country": country or None,
            "birth_date": None,
            "positions": set(),
            "teams": set(),
            "seasons": set(),
            "competitions": set(),
            "matches": set(),
            "jersey_numbers": {},
            "date_range": {"first": None, "last": None},
            "match_count": 0,
        })
        if name:
            for key in _key_variants(name):
                # Note: If collision, keep first seen
                self.player_name_index.setdefault(key, player_id)
        if country:
            self.player_by_country[country].append(player_id)

    def _ensure_manager(self, manager_id: int, name: str) -> None:
        node = self.managers.setdefault(manager_id, {
            "id": manager_id,
            "name": name or None,
            "teams": set(),
            "seasons": set(),
            "date_ranges": {},  # team_id -> [start,end] if known
        })
        if name:
            for key in _key_variants(name):
                self.manager_name_index.setdefault(key, manager_id)

    @staticmethod
    def _update_date_range(dr: Dict[str, Optional[str]], date_str: Optional[str]) -> None:
        if not date_str:
            return
        try:
            # Expect YYYY-MM-DD
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        except Exception:
            return
        if not dr.get("start") or dt < datetime.strptime(dr["start"], "%Y-%m-%d"):
            dr["start"] = dt.strftime("%Y-%m-%d")
        if not dr.get("end") or dt > datetime.strptime(dr["end"], "%Y-%m-%d"):
            dr["end"] = dt.strftime("%Y-%m-%d")

    def _finalize_season(self, competition_id: int, season_id: int) -> None:
        # Teams already updated via matches; update team aggregates
        for team_id in list(self.season_to_teams.get(season_id, [])):
            self.teams[team_id]["seasons"].add(season_id)
            self.teams[team_id]["competitions"].add(competition_id)
        # Match count per team
        for match_id in list(self.season_to_matches.get(season_id, [])):
            m = self.matches.get(match_id) or {}
            for t_id in (m.get("home_team_id"), m.get("away_team_id")):
                if isinstance(t_id, int):
                    self.teams[t_id]["match_count"] += 1

    # -------------------- Finalization and write --------------------
    def _finalize_and_write(self) -> None:
        # Convert sets → lists and fill denormalized fields
        for team in self.teams.values():
            team["seasons"] = sorted(team.get("seasons", set()))
            team["competitions"] = sorted(team.get("competitions", set()))
            # Managers from aggregated map
            managers = self.manager_by_team.get(team["id"], [])
            team["managers"] = sorted(set(managers))
            team["players"] = sorted(self.team_to_players.get(team["id"], set()))

        for player_id, player in self.players.items():
            # First/last appearance from matches
            match_dates = []
            for mid in self.player_to_matches.get(player_id, set()):
                md = self.matches.get(mid, {}).get("match_date")
                if md:
                    match_dates.append(md)
            if match_dates:
                player["date_range"]["first"] = min(match_dates)
                player["date_range"]["last"] = max(match_dates)
            player["teams"] = sorted(player.get("teams", set()))
            player["seasons"] = sorted(self.player_to_seasons.get(player_id, set()))
            # competitions via seasons
            comps: Set[int] = set()
            for s in player["seasons"]:
                comp_id = self.seasons.get(s, {}).get("competition_id")
                if isinstance(comp_id, int):
                    comps.add(comp_id)
            player["competitions"] = sorted(comps)
            player["matches"] = sorted(self.player_to_matches.get(player_id, set()))
            player["match_count"] = len(player["matches"])
            # positions already set (set -> list)
            player["positions"] = sorted(player.get("positions", set()))

        for manager in self.managers.values():
            manager["teams"] = sorted(manager.get("teams", set()))
            manager["seasons"] = sorted(manager.get("seasons", set()))

        # Season teams to list and by_season map
        for season_id, season in self.seasons.items():
            season["teams"] = sorted(self.season_to_teams.get(season_id, set()))
            self.team_by_season[season_id] = list(season["teams"])

        # Build indices payloads
        competitions_index = {
            "generated_at": _now_iso(),
            "by_id": self.competitions,
            "by_name": self.competition_name_index,
            "by_country": self.competition_by_country,
            "by_type": self.competition_by_type,
        }

        seasons_index = {
            "generated_at": _now_iso(),
            "by_id": self.seasons,
            "by_year": self.season_by_year,
            "by_competition": {str(cid): sorted(list(sids)) for cid, sids in self.comp_to_seasons.items()},
        }

        teams_index = {
            "generated_at": _now_iso(),
            "by_id": self.teams,
            "by_name": self.team_name_index,
            "by_country": self.team_by_country,
            "by_season": self.team_by_season,
        }

        players_index = {
            "generated_at": _now_iso(),
            "by_id": self.players,
            "by_name": self.player_name_index,
            "by_team": {str(tid): sorted(list(pids)) for tid, pids in self.team_to_players.items()},
            "by_season": {str(sid): sorted(list(pids)) for sid, pids in self.player_by_season.items()},
            "by_position": self.player_by_position,
            "by_country": self.player_by_country,
        }

        managers_index = {
            "generated_at": _now_iso(),
            "by_id": self.managers,
            "by_name": self.manager_name_index,
            "by_team": {str(tid): vids for tid, vids in self.manager_by_team.items()},
            "by_season": {str(sid): vids for sid, vids in self.manager_by_season.items()},
        }

        matches_index = {
            "generated_at": _now_iso(),
            "by_id": self.matches,
        }

        relationship_graph = {
            "generated_at": _now_iso(),
            "competition_to_seasons": {str(cid): sorted(list(sids)) for cid, sids in self.comp_to_seasons.items()},
            "season_to_teams": {str(sid): sorted(list(tids)) for sid, tids in self.season_to_teams.items()},
            "season_to_players": {str(sid): sorted(list(pids)) for sid, pids in self.season_to_players.items()},
            "team_to_seasons": {str(tid): sorted(list(sids)) for tid, sids in self.team_to_seasons.items()},
            "team_to_players": {str(tid): sorted(list(pids)) for tid, pids in self.team_to_players.items()},
            "player_to_teams": {str(pid): sorted(list(tids)) for pid, tids in self.player_to_teams.items()},
            "player_to_seasons": {str(pid): sorted(list(sids)) for pid, sids in self.player_to_seasons.items()},
            "player_to_matches": {str(pid): sorted(list(mids)) for pid, mids in self.player_to_matches.items()},
            "season_to_matches": {str(sid): sorted(list(mids)) for sid, mids in self.season_to_matches.items()},
            "match_to_players": {str(mid): sorted(list(pids)) for mid, pids in self.match_to_players.items()},
        }

        stats_summary = self._build_stats_summary()
        validation_report = self._validate()

        # Write outputs
        self._write_json(self.cfg.paths.competitions, competitions_index)
        self._write_json(self.cfg.paths.seasons, seasons_index)
        self._write_json(self.cfg.paths.teams, teams_index)
        self._write_json(self.cfg.paths.players, players_index)
        self._write_json(self.cfg.paths.managers, managers_index)
        self._write_json(self.cfg.paths.matches, matches_index)
        self._write_json(self.cfg.paths.relationships, relationship_graph)
        self._write_json(self.cfg.paths.stats, stats_summary)
        self._write_json(self.cfg.paths.validation, validation_report)
        self._write_guide()

    def _build_stats_summary(self) -> Dict[str, Any]:
        date_start: Optional[str] = None
        date_end: Optional[str] = None
        for comp in self.competitions.values():
            dr = comp.get("date_range") or {}
            if dr.get("start") and (not date_start or dr["start"] < date_start):
                date_start = dr["start"]
            if dr.get("end") and (not date_end or dr["end"] > date_end):
                date_end = dr["end"]
        return {
            "generated_at": _now_iso(),
            "counts": {
                "competitions": len(self.competitions),
                "seasons": len(self.seasons),
                "teams": len(self.teams),
                "players": len(self.players),
                "managers": len(self.managers),
                "matches": len(self.matches),
            },
            "date_coverage": {"start": date_start, "end": date_end},
        }

    def _validate(self) -> Dict[str, Any]:
        issues: List[str] = []
        # Uniqueness checks
        if len(self.competitions) != len({c["id"] for c in self.competitions.values()}):
            issues.append("Duplicate competition IDs detected")
        if len(self.seasons) != len({s["id"] for s in self.seasons.values()}):
            issues.append("Duplicate season IDs detected")

        # Relationship consistency
        for sid, season in self.seasons.items():
            cid = season.get("competition_id")
            if isinstance(cid, int) and sid not in self.comp_to_seasons.get(cid, set()):
                issues.append(f"Season {sid} not linked back to competition {cid}")
        for tid, team in self.teams.items():
            for sid in team.get("seasons", []):
                if tid not in self.season_to_teams.get(sid, set()):
                    issues.append(f"Team {tid} not present in season_to_teams[{sid}]")
        for pid, player in self.players.items():
            for tid in player.get("teams", []):
                if pid not in self.team_to_players.get(tid, set()):
                    issues.append(f"Player {pid} not present in team_to_players[{tid}]")

        issues.extend(self.validation_issues)
        return {"generated_at": _now_iso(), "issues": issues}

    # -------------------- IO --------------------
    @staticmethod
    def _write_json(path: Path, obj: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(obj, f)

    def _write_guide(self) -> None:
        guide = f"""
# Quick Lookup Guide

Generated: {_now_iso()}

Files written under `{self.cfg.paths.base_dir}`:
- `competitions_index.json` – by_id, by_name, by_country, by_type
- `seasons_index.json` – by_id, by_year, by_competition
- `teams_index.json` – by_id, by_name, by_country, by_season
- `players_index.json` – by_id, by_name, by_team, by_season, by_position, by_country
- `managers_index.json` – by_id, by_name, by_team, by_season
- `matches_index.json` – by_id (summary per match)
- `relationship_graph.json` – cross-entity links for instant traversal
- `stats_summary.json` – counts and date coverage
- `validation_report.json` – relationship integrity checks

Usage pattern examples (Python):

```python
import json, pathlib
root = pathlib.Path('{self.cfg.paths.base_dir.as_posix()}')
players = json.loads((root / 'players_index.json').read_text())
teams = json.loads((root / 'teams_index.json').read_text())
rels = json.loads((root / 'relationship_graph.json').read_text())

# Find Messi by name (exact or canonicalized) – near O(1)
pid = players['by_name'].get('messi') or players['by_name'].get('lionel messi')
player = players['by_id'][str(pid)] if isinstance(pid, int) else players['by_id'][pid]

# All matches for player in a given season
season_id = ...
match_ids = set(rels['player_to_matches'][str(pid)])
season_matches = set(rels['season_to_matches'][str(season_id)])
player_matches_in_season = sorted(match_ids & season_matches)

# Team roster for a season
team_id = ...
roster = [players['by_id'][str(p)] for p in rels['team_to_players'][str(team_id)]]
```

Performance tips:
- Use the direct maps (by_id, by_name) for single-entity lookups.
- Use the `relationship_graph.json` to traverse between entities without scanning.
- Use canonical keys (lowercase, punctuation removed) for fuzzy-ish matching.

API provenance:
- competitions: v4 competitions
- seasons: v6 seasons
- matches: v6 matches
- lineups: v4 lineups
- player season stats: v4 player season stats (if enabled)

Notes:
- Some attributes (e.g., manager date ranges, player birth dates) depend on API availability; fields may be null when not present.
- Rebuild the index periodically to refresh data; see the build entrypoint in `statsbomb_db_index.py`.
```
"""
        self.cfg.paths.guide.write_text(guide, encoding="utf-8")


def build_full_index(
    competitions: Optional[Iterable[int]] = None,
    *,
    include_player_stats: bool = True,
    include_lineups: bool = True,
) -> IndexPaths:
    cfg = IndexBuildConfig(
        competitions=competitions,
        include_player_stats=include_player_stats,
        include_lineups=include_lineups,
    )
    indexer = StatsBombDBIndexer(cfg)
    indexer.build()
    return cfg.paths


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    # Build full index across all competitions (may take time; uses cache)
    build_full_index()
