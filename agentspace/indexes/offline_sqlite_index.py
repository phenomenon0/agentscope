"""
Build a lightweight SQLite index covering top-tier competitions for offline lookup.

The resulting database provides three tables—`competitions`, `teams`, `players`—
along with FTS-powered companion tables for fuzzy name search.  It is tailored
to the top ten domestic leagues plus key continental cups (Champions League,
Europa League, Europa Conference League, and the English League Cup).
"""
from __future__ import annotations

import difflib
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..clients.statsbomb import StatsBombClient
from ..exceptions import APINotFoundError
from ..services.statsbomb_tools import season_id_for_label

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Competition specifications
# ---------------------------------------------------------------------------


def _canonical(text: Optional[str]) -> str:
    return "".join((text or "").lower().split())


@dataclass(frozen=True)
class CompetitionSpec:
    name: str
    category: str  # "league" or "cup"
    competition_id: Optional[int] = None
    aliases: Tuple[str, ...] = ()
    max_seasons: int = 4
    season_labels: Tuple[str, ...] = ()

PRIORITY_COMPETITIONS: Tuple[CompetitionSpec, ...] = (
    CompetitionSpec("Premier League", "league", aliases=("england premier league",), max_seasons=4),
    CompetitionSpec("La Liga", "league", aliases=("laliga", "la liga santander"), max_seasons=4),
    CompetitionSpec("Bundesliga", "league", aliases=("germany bundesliga",), max_seasons=4),
    CompetitionSpec("Serie A", "league", aliases=("italy serie a",), max_seasons=4),
    CompetitionSpec("Ligue 1", "league", aliases=("france ligue 1",), max_seasons=4),
    CompetitionSpec("Eredivisie", "league", aliases=("netherlands eredivisie",), max_seasons=3),
    CompetitionSpec("Primeira Liga", "league", aliases=("portugal primeira liga", "liga portugal"), max_seasons=3),
    CompetitionSpec("Jupiler Pro League", "league", aliases=("belgium pro league", "belgian pro league"), max_seasons=3),
    CompetitionSpec("Championship", "league", aliases=("efl championship", "english championship"), max_seasons=3),
    CompetitionSpec("Major League Soccer", "league", aliases=("mls",), max_seasons=3),
    CompetitionSpec("UEFA Champions League", "cup", aliases=("champions league",), max_seasons=3),
    CompetitionSpec("UEFA Europa League", "cup", aliases=("europa league",), max_seasons=3),
    CompetitionSpec("UEFA Europa Conference League", "cup", aliases=("europa conference league",), max_seasons=3),
    CompetitionSpec("EFL Cup", "cup", aliases=("carabao cup", "english league cup", "football league cup"), max_seasons=2),
)


DEFAULT_SEASON_LABELS: Tuple[str, ...] = (
    "2025/2026",
    "2024/2025",
    "2023/2024",
    "2022/2023",
)


@dataclass
class OfflineIndexBuilder:
    """
    Create an FTS-enabled SQLite database enumerating competitions, teams, and players.
    """

    db_path: Path = Path(".cache/offline_index/top_competitions.sqlite")
    competitions: Optional[Sequence[CompetitionSpec]] = None
    client: StatsBombClient = field(default_factory=StatsBombClient)

    def build(self) -> Path:
        """
        Build the SQLite database from the configured competitions.
        """

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.exists():
            self.db_path.unlink()

        catalogue = self._competition_catalogue()
        candidate_specs = (
            list(self.competitions)
            if self.competitions is not None
            else self._auto_competitions_from_catalogue(catalogue)
        )
        resolved_specs = self._resolve_competitions(catalogue, candidate_specs)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.row_factory = sqlite3.Row
            self._create_schema(conn)

            for spec in resolved_specs:
                LOGGER.info("Building index for %s (%s)", spec.name, spec.competition_id)
                seasons = self._resolve_seasons_for_spec(spec)
                if not seasons:
                    LOGGER.warning(
                        "Skipping competition %s (%s); no seasons available.",
                        spec.name,
                        spec.competition_id,
                    )
                    continue
                for season_id, season_name in seasons:
                    self._ingest_season(conn, spec, season_id, season_name)

            self._populate_fts(conn)
            self._create_indexes(conn)
            conn.commit()

        LOGGER.info("SQLite index written to %s", self.db_path)
        return self.db_path

    # ------------------------------------------------------------------ utils

    def _competition_catalogue(self) -> List[Dict[str, Any]]:
        rows = self.client.list_competitions(use_cache=True) or []
        return rows

    def _resolve_competitions(
        self,
        catalogue: Iterable[Dict[str, Any]],
        specs: Sequence[CompetitionSpec],
    ) -> List[CompetitionSpec]:
        """
        Ensure every spec has a competition_id, resolving by name/alias if needed.
        """

        lookup: dict[str, int] = {}
        countries: dict[int, str] = {}
        formats: dict[int, str] = {}
        names: dict[int, str] = {}

        for row in catalogue:
            comp_id = row.get("competition_id")
            name = row.get("competition_name") or ""
            if comp_id is None:
                continue
            lookup.setdefault(_canonical(name), int(comp_id))
            countries[int(comp_id)] = row.get("country_name")
            formats[int(comp_id)] = row.get("competition_format")
            names[int(comp_id)] = name

        resolved: List[CompetitionSpec] = []
        for spec in specs:
            if spec.competition_id:
                resolved.append(spec)
                continue

            candidates = [_canonical(spec.name)] + [_canonical(alias) for alias in spec.aliases]
            comp_id: Optional[int] = None
            for key in candidates:
                comp_id = lookup.get(key)
                if comp_id:
                    break
            if not comp_id:
                fuzzy_matches = difflib.get_close_matches(
                    _canonical(spec.name), lookup.keys(), n=1, cutoff=0.75
                )
                if fuzzy_matches:
                    comp_id = lookup.get(fuzzy_matches[0])

            if not comp_id:
                LOGGER.warning(
                    "Skipping competition '%s' because its ID could not be resolved from StatsBomb catalogue.",
                    spec.name,
                )
                continue

            resolved.append(
                CompetitionSpec(
                    name=names.get(comp_id, spec.name),
                    category=spec.category,
                    competition_id=comp_id,
                    aliases=spec.aliases,
                    max_seasons=spec.max_seasons,
                )
            )
        return resolved

    def _auto_competitions_from_catalogue(
        self,
        catalogue: Iterable[Dict[str, Any]],
    ) -> List[CompetitionSpec]:
        lookup: dict[str, Dict[str, Any]] = {}
        for row in catalogue:
            comp_id = row.get("competition_id")
            name = row.get("competition_name")
            if comp_id is None or not name:
                continue
            key = _canonical(name)
            lookup[key] = {
                "competition_id": int(comp_id),
                "competition_name": name,
            }

        specs: List[CompetitionSpec] = []
        seen_ids: set[int] = set()

        for spec in PRIORITY_COMPETITIONS:
            candidates = [spec.name, *spec.aliases]
            match_info: Optional[Dict[str, Any]] = None
            for candidate in candidates:
                match_info = lookup.get(_canonical(candidate))
                if match_info:
                    break

            if not match_info:
                # Fuzzy fallback
                possible = difflib.get_close_matches(
                    _canonical(spec.name),
                    list(lookup.keys()),
                    n=1,
                    cutoff=0.82,
                )
                if possible:
                    match_info = lookup.get(possible[0])

            if not match_info:
                continue

            specs.append(
                CompetitionSpec(
                    name=match_info["competition_name"],
                    category=spec.category,
                    competition_id=match_info["competition_id"],
                    aliases=spec.aliases,
                    max_seasons=spec.max_seasons,
                    season_labels=spec.season_labels,
                )
            )
            seen_ids.add(match_info["competition_id"])

        target_count = min(12, len(lookup))
        if len(seen_ids) < target_count:
            for row in catalogue:
                comp_id = row.get("competition_id")
                name = row.get("competition_name")
                if comp_id is None or not name:
                    continue
                comp_id = int(comp_id)
                if comp_id in seen_ids:
                    continue
                fmt = (row.get("competition_format") or "").lower()
                if "league" in fmt:
                    category = "league"
                elif "cup" in fmt or "champions" in name.lower():
                    category = "cup"
                else:
                    continue

                specs.append(
                    CompetitionSpec(
                        name=name,
                        category=category,
                        competition_id=comp_id,
                        aliases=(),
                        max_seasons=2,
                        season_labels=(),
                    )
                )
                seen_ids.add(comp_id)
                if len(seen_ids) >= target_count:
                    break

        if not specs:
            LOGGER.warning(
                "No priority competitions matched the StatsBomb catalogue; the offline index will be empty."
            )

        return specs

    # ---------------------------------------------------------------- ingest

    def _ingest_season(
        self,
        conn: sqlite3.Connection,
        spec: CompetitionSpec,
        season_id: int,
        season_name: str,
    ) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO competitions (
                competition_id,
                season_id,
                competition_name,
                season_name,
                competition_category,
                country,
                competition_stage
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                spec.competition_id,
                season_id,
                spec.name,
                season_name,
                spec.category,
                None,
                "",
            ),
        )

        teams, matches = self._collect_teams(spec, season_id, season_name)
        self._insert_teams(conn, spec, season_id, season_name, teams)

        self._insert_matches(conn, spec, season_id, season_name, matches)

        match_players = self._collect_match_players(spec, season_id, season_name, matches)
        self._insert_match_players(conn, spec, season_id, season_name, match_players)

        players = self._collect_players(spec, season_id, season_name, teams, matches)
        self._insert_players(conn, spec, season_id, season_name, players)

    def _resolve_seasons_for_spec(self, spec: CompetitionSpec) -> List[Tuple[int, str]]:
        seasons: List[Tuple[int, str]] = []
        seen_ids: set[int] = set()

        try:
            api_seasons = self.client.list_seasons(spec.competition_id, use_cache=True) or []
        except APINotFoundError:
            api_seasons = []
        except Exception as exc:  # pragma: no cover
            LOGGER.warning(
                "Failed to list seasons for %s (%s): %s",
                spec.name,
                spec.competition_id,
                exc,
            )
            api_seasons = []

        if api_seasons:
            sorted_rows = sorted(
                api_seasons,
                key=lambda row: row.get("season_id") or 0,
                reverse=True,
            )
            for row in sorted_rows:
                sid = row.get("season_id")
                if not isinstance(sid, int):
                    continue
                if sid in seen_ids:
                    continue
                seasons.append((sid, row.get("season_name") or ""))
                seen_ids.add(sid)
                if len(seasons) >= spec.max_seasons:
                    break

        if len(seasons) >= spec.max_seasons:
            return seasons[: spec.max_seasons]

        labels = spec.season_labels or DEFAULT_SEASON_LABELS
        for label in labels:
            if len(seasons) >= spec.max_seasons:
                break
            try:
                season_id = season_id_for_label(
                    spec.competition_id,
                    label,
                    use_cache=True,
                )
            except Exception:  # pragma: no cover
                continue
            if season_id is None or season_id in seen_ids:
                continue
            seasons.append((season_id, label))
            seen_ids.add(season_id)

        return seasons[: spec.max_seasons]

    def _collect_teams(
        self,
        spec: CompetitionSpec,
        season_id: int,
        season_name: str,
    ) -> Tuple[List[dict], List[dict]]:
        try:
            team_stats = self.client.get_team_season_stats(
                spec.competition_id,
                season_id,
                use_cache=True,
            )
        except Exception as exc:  # pragma: no cover - tolerate missing stats
            LOGGER.warning(
                "Team season stats unavailable for %s %s: %s",
                spec.name,
                season_name,
                exc,
            )
            team_stats = []

        teams: dict[int, dict] = {}
        if team_stats:
            for row in team_stats:
                team_id = row.get("team_id") or (row.get("team") or {}).get("team_id")
                team_name = row.get("team_name") or (row.get("team") or {}).get("team_name")
                if not team_id or not team_name:
                    continue
                teams[int(team_id)] = {
                    "team_id": int(team_id),
                    "team_name": team_name,
                }

        matches: List[dict] = []
        if not teams:
            try:
                matches = self.client.list_matches(
                    spec.competition_id,
                    season_id,
                    use_cache=True,
                ) or []
            except Exception as exc:  # pragma: no cover
                LOGGER.warning(
                    "Matches unavailable for %s %s: %s",
                    spec.name,
                    season_name,
                    exc,
                )
                matches = []
            for match in matches:
                for side in ("home_team", "away_team"):
                    team = match.get(side) or {}
                    team_id = team.get("team_id")
                    team_name = team.get("team_name")
                    if team_id and team_name:
                        teams[int(team_id)] = {
                            "team_id": int(team_id),
                            "team_name": team_name,
                        }
        else:
            try:
                matches = self.client.list_matches(
                    spec.competition_id,
                    season_id,
                    use_cache=True,
                ) or []
            except Exception as exc:  # pragma: no cover
                LOGGER.warning(
                    "Matches unavailable for %s %s: %s",
                    spec.name,
                    season_name,
                    exc,
                )
                matches = []

        return list(teams.values()), matches

    def _collect_players(
        self,
        spec: CompetitionSpec,
        season_id: int,
        season_name: str,
        teams: List[dict],
        matches: List[dict],
    ) -> List[dict]:
        try:
            player_stats = self.client.get_player_season_stats(
                spec.competition_id,
                season_id,
                use_cache=True,
            )
        except Exception as exc:  # pragma: no cover
            LOGGER.warning(
                "Player season stats unavailable for %s %s: %s",
                spec.name,
                season_name,
                exc,
            )
            player_stats = []

        players: dict[int, dict] = {}
        if player_stats:
            for row in player_stats:
                player_id = row.get("player_id")
                player_name = row.get("player_name")
                team_id = row.get("team_id") or (row.get("team") or {}).get("team_id")
                team_name = row.get("team_name") or (row.get("team") or {}).get("team_name")
                position = row.get("position") or row.get("player_position")
                minutes = (
                    row.get("player_season_minutes")
                    or row.get("minutes_played")
                    or row.get("player_minutes")
                )
                if not player_id or not player_name:
                    continue
                players[int(player_id)] = {
                    "player_id": int(player_id),
                    "player_name": player_name,
                    "team_id": int(team_id) if team_id else None,
                    "team_name": team_name,
                    "position": position,
                    "minutes": minutes,
                }

        if players:
            return list(players.values())

        processed_matches = 0
        for match in matches:
            if processed_matches >= 20:
                break
            match_id = match.get("match_id")
            if not match_id:
                continue
            processed_matches += 1
            try:
                lineups = self.client.get_lineups(match_id, use_cache=True) or []
            except Exception:  # pragma: no cover - tolerate missing lineups
                continue
            for entry in lineups:
                team_id = entry.get("team_id")
                team_name = entry.get("team_name")
                for player in entry.get("lineup", []):
                    player_id = player.get("player_id")
                    player_name = player.get("player_name")
                    position = player.get("position") or player.get("player_position")
                    jersey_number = player.get("jersey_number")
                    if not player_id or not player_name:
                        continue
                    players.setdefault(
                        int(player_id),
                        {
                            "player_id": int(player_id),
                            "player_name": player_name,
                            "team_id": int(team_id) if team_id else None,
                            "team_name": team_name,
                            "position": position,
                            "minutes": None,
                            "jersey_number": jersey_number,
                        },
                    )

        if not players:
            LOGGER.warning(
                "Failed to collect player data for %s season %s",
                spec.name,
                season_name,
            )
        return list(players.values())

    def _insert_matches(
        self,
        conn: sqlite3.Connection,
        spec: CompetitionSpec,
        season_id: int,
        season_name: str,
        matches: List[dict],
    ) -> None:
        if not matches:
            return
        rows = []
        for match in matches:
            match_id = match.get("match_id")
            if not match_id:
                continue
            stage = match.get("competition_stage")
            if isinstance(stage, dict):
                stage = stage.get("name")
            status = (match.get("match_status") or "").lower()
            if status and status not in {"available", "played", "postponed"}:
                continue
            home_team = match.get("home_team") or {}
            away_team = match.get("away_team") or {}

            def _to_int(value: Any) -> Optional[int]:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None

            home_team_id = _to_int(home_team.get("home_team_id") or home_team.get("team_id"))
            away_team_id = _to_int(away_team.get("away_team_id") or away_team.get("team_id"))

            def _to_score(value: Any) -> Optional[int]:
                if isinstance(value, dict):
                    value = value.get("score") or value.get("value")
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None

            rows.append(
                (
                    match_id,
                    spec.competition_id,
                    season_id,
                    spec.name,
                    season_name,
                    match.get("match_date") or match.get("match_date_utc"),
                    match.get("kick_off") or match.get("kick_off_utc"),
                    (match.get("stadium") or {}).get("name"),
                    home_team_id,
                    home_team.get("home_team_name") or home_team.get("team_name"),
                    away_team_id,
                    away_team.get("away_team_name") or away_team.get("team_name"),
                    _to_score(match.get("home_score") or match.get("home_goals")),
                    _to_score(match.get("away_score") or match.get("away_goals")),
                    stage,
                )
            )
        if not rows:
            return
        conn.executemany(
            """
            INSERT OR IGNORE INTO matches (
                match_id,
                competition_id,
                season_id,
                competition_name,
                season_name,
                match_date,
                kick_off,
                stadium_name,
                home_team_id,
                home_team_name,
                away_team_id,
                away_team_name,
                home_score,
                away_score,
                competition_stage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def _collect_match_players(
        self,
        spec: CompetitionSpec,
        season_id: int,
        season_name: str,
        matches: List[dict],
    ) -> List[dict]:
        participants: List[dict] = []
        seen: set[tuple[int, int]] = set()

        def _to_int(value: Any) -> Optional[int]:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        for match in matches:
            match_id = match.get("match_id")
            if not match_id:
                continue
            try:
                lineups = self.client.get_lineups(match_id, use_cache=True) or []
            except Exception as exc:  # pragma: no cover - tolerate missing lineups
                LOGGER.warning(
                    "Lineups unavailable for match %s in competition %s: %s",
                    match_id,
                    spec.name,
                    exc,
                )
                continue
            for entry in lineups:
                team_id = _to_int(entry.get("team_id"))
                team_name = entry.get("team_name")
                for player in entry.get("lineup", []):
                    player_id = player.get("player_id")
                    player_name = player.get("player_name")
                    if not player_id or not player_name:
                        continue
                    pid = _to_int(player_id)
                    if pid is None:
                        continue
                    key = (match_id, pid)
                    if key in seen:
                        continue
                    seen.add(key)
                    participants.append(
                        {
                            "match_id": match_id,
                            "player_id": pid,
                            "team_id": team_id,
                            "competition_id": spec.competition_id,
                            "season_id": season_id,
                            "competition_name": spec.name,
                            "season_name": season_name,
                            "player_name": player_name,
                            "team_name": team_name,
                            "position": player.get("position") or player.get("player_position"),
                            "jersey_number": str(player.get("jersey_number")) if player.get("jersey_number") is not None else None,
                            "is_starter": 1 if any(
                                (pos.get("start_reason") or "").lower().startswith("starting")
                                for pos in (player.get("positions") or [])
                            )
                            else 0,
                            "minutes_played": player.get("minutes_played") or player.get("player_minutes"),
                        }
                    )
        return participants

    def _insert_match_players(
        self,
        conn: sqlite3.Connection,
        spec: CompetitionSpec,
        season_id: int,
        season_name: str,
        participants: List[dict],
    ) -> None:
        if not participants:
            return
        rows = []
        for record in participants:
            rows.append(
                (
                    record.get("match_id"),
                    record.get("player_id"),
                    record.get("team_id"),
                    record.get("competition_id"),
                    record.get("season_id"),
                    record.get("competition_name"),
                    record.get("season_name"),
                    record.get("player_name"),
                    record.get("team_name"),
                    record.get("position"),
                    record.get("jersey_number"),
                    record.get("is_starter"),
                    record.get("minutes_played"),
                )
            )
        conn.executemany(
            """
            INSERT OR IGNORE INTO match_players (
                match_id,
                player_id,
                team_id,
                competition_id,
                season_id,
                competition_name,
                season_name,
                player_name,
                team_name,
                position,
                jersey_number,
                is_starter,
                minutes_played
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    # ---------------------------------------------------------------- insert

    def _insert_teams(
        self,
        conn: sqlite3.Connection,
        spec: CompetitionSpec,
        season_id: int,
        season_name: str,
        teams: List[dict],
    ) -> None:
        if not teams:
            return
        conn.executemany(
            """
            INSERT OR IGNORE INTO teams (
                team_id,
                team_name,
                competition_id,
                season_id,
                season_name,
                competition_name,
                competition_category
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    team["team_id"],
                    team["team_name"],
                    spec.competition_id,
                    season_id,
                    season_name,
                    spec.name,
                    spec.category,
                )
                for team in teams
            ],
        )

    def _insert_players(
        self,
        conn: sqlite3.Connection,
        spec: CompetitionSpec,
        season_id: int,
        season_name: str,
        players: List[dict],
    ) -> None:
        if not players:
            return
        conn.executemany(
            """
            INSERT OR IGNORE INTO players (
                player_id,
                player_name,
                competition_id,
                season_id,
                team_id,
                team_name,
                season_name,
                competition_name,
                competition_category,
                position,
                minutes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    player["player_id"],
                    player["player_name"],
                    spec.competition_id,
                    season_id,
                    player.get("team_id"),
                    player.get("team_name"),
                    season_name,
                    spec.name,
                    spec.category,
                    player.get("position"),
                    player.get("minutes"),
                )
                for player in players
            ],
        )

    # ---------------------------------------------------------------- schema

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE competitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competition_id INTEGER NOT NULL,
                season_id INTEGER NOT NULL,
                competition_name TEXT NOT NULL,
                season_name TEXT NOT NULL,
                competition_category TEXT NOT NULL,
                country TEXT,
                competition_stage TEXT,
                UNIQUE (competition_id, season_id)
            );

            CREATE TABLE teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                team_name TEXT NOT NULL,
                competition_id INTEGER NOT NULL,
                season_id INTEGER NOT NULL,
                season_name TEXT NOT NULL,
                competition_name TEXT NOT NULL,
                competition_category TEXT NOT NULL,
                UNIQUE (team_id, competition_id, season_id)
            );

            CREATE TABLE players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                competition_id INTEGER NOT NULL,
                season_id INTEGER NOT NULL,
                team_id INTEGER,
                team_name TEXT,
                season_name TEXT NOT NULL,
                competition_name TEXT NOT NULL,
                competition_category TEXT NOT NULL,
                position TEXT,
                minutes REAL,
                UNIQUE (player_id, competition_id, season_id)
            );

            CREATE TABLE matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                competition_id INTEGER NOT NULL,
                season_id INTEGER NOT NULL,
                competition_name TEXT NOT NULL,
                season_name TEXT NOT NULL,
                match_date TEXT,
                kick_off TEXT,
                stadium_name TEXT,
                home_team_id INTEGER,
                home_team_name TEXT,
                away_team_id INTEGER,
                away_team_name TEXT,
                home_score INTEGER,
                away_score INTEGER,
                competition_stage TEXT,
                UNIQUE (match_id)
            );

            CREATE TABLE match_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                team_id INTEGER,
                competition_id INTEGER NOT NULL,
                season_id INTEGER NOT NULL,
                competition_name TEXT NOT NULL,
                season_name TEXT NOT NULL,
                player_name TEXT,
                team_name TEXT,
                position TEXT,
                jersey_number TEXT,
                is_starter INTEGER,
                minutes_played REAL,
                UNIQUE (match_id, player_id, team_id)
            );

            CREATE VIRTUAL TABLE competitions_fts
            USING fts5(
                competition_name,
                season_name,
                competition_category,
                content='competitions',
                content_rowid='id'
            );

            CREATE VIRTUAL TABLE teams_fts
            USING fts5(
                team_name,
                competition_name,
                season_name,
                content='teams',
                content_rowid='id'
            );

            CREATE VIRTUAL TABLE players_fts
            USING fts5(
                player_name,
                team_name,
                competition_name,
                content='players',
                content_rowid='id'
            );
            """
        )

    def _populate_fts(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            INSERT INTO competitions_fts(rowid, competition_name, season_name, competition_category)
            SELECT id, competition_name, season_name, competition_category FROM competitions;

            INSERT INTO teams_fts(rowid, team_name, competition_name, season_name)
            SELECT id, team_name, competition_name, season_name FROM teams;

            INSERT INTO players_fts(rowid, player_name, team_name, competition_name)
            SELECT id, player_name, team_name, competition_name FROM players;
            """
        )

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE INDEX idx_competitions_comp_season
            ON competitions(competition_id, season_id);

            CREATE INDEX idx_teams_comp_season
            ON teams(competition_id, season_id);

            CREATE INDEX idx_teams_name
            ON teams(team_name COLLATE NOCASE);

            CREATE INDEX idx_players_comp_season
            ON players(competition_id, season_id);

            CREATE INDEX idx_players_team
            ON players(team_id, competition_id, season_id);

            CREATE INDEX idx_players_name
            ON players(player_name COLLATE NOCASE);

            CREATE INDEX idx_matches_comp_season
            ON matches(competition_id, season_id);

            CREATE INDEX idx_matches_team
            ON matches(home_team_id, away_team_id);

            CREATE INDEX idx_match_players_match
            ON match_players(match_id);

            CREATE INDEX idx_match_players_player
            ON match_players(player_id);
            """
        )


def build_default_index() -> Path:
    """
    Convenience function used by `python -m agentspace.indexes.offline_sqlite_index`.
    """

    builder = OfflineIndexBuilder()
    return builder.build()


if __name__ == "__main__":  # pragma: no cover - manual invocation
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build_default_index()
