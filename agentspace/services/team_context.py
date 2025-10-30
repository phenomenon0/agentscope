"""Helpers for building team-centric context blocks."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from time import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .statsbomb_tools import (
    fetch_team_season_stats_data,
    get_competition_players,
    list_competitions,
    list_matches,
    season_id_for_label,
)
from .data_fetch import get_statsbomb_client

Number = float | int


@dataclass(frozen=True)
class TeamRecord:
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    def to_dict(self) -> Dict[str, int]:
        return {
            "played": self.played,
            "won": self.won,
            "drawn": self.drawn,
            "lost": self.lost,
            "goals_for": self.goals_for,
            "goals_against": self.goals_against,
            "goal_difference": self.goal_difference,
        }


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalise_name(name: Optional[str]) -> str:
    return (name or "").strip().casefold()


def _compute_goal_difference(row: Dict[str, Any]) -> float:
    if "team_season_goal_difference" in row and row["team_season_goal_difference"] is not None:
        return _to_float(row["team_season_goal_difference"])
    goals = _to_float(row.get("team_season_goals"))
    conceded = _to_float(row.get("team_season_goals_against"))
    return goals - conceded


def _sort_table(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ordered: List[Dict[str, Any]] = []
    for row in rows:
        enriched = copy.deepcopy(row)
        enriched["goal_difference"] = _compute_goal_difference(row)
        enriched["team_season_points"] = _to_float(row.get("team_season_points"))
        enriched["team_season_matches"] = _to_float(row.get("team_season_matches"))
        enriched["team_season_goals"] = _to_float(row.get("team_season_goals"))
        ordered.append(enriched)

    ordered.sort(
        key=lambda item: (
            -item.get("team_season_points", 0.0),
            -item.get("goal_difference", 0.0),
            -item.get("team_season_goals", 0.0),
        )
    )

    for idx, row in enumerate(ordered, start=1):
        row["position"] = idx

    return ordered


def _find_team_row(team_name: str, table: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    target = _normalise_name(team_name)
    for row in table:
        if _normalise_name(row.get("team_name")) == target:
            return row
    return None


def _parse_match_datetime(match: Dict[str, Any]) -> Optional[datetime]:
    date_str = match.get("match_date")
    if not date_str:
        return None
    time_str = match.get("kick_off") or ""
    if time_str:
        time_str = time_str.split(".")[0]
        combined = f"{date_str} {time_str}"
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(combined, fmt)
            except ValueError:
                continue
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


def _summarise_matches(team_name: str, matches: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], TeamRecord]:
    played: List[Dict[str, Any]] = []
    upcoming: List[Dict[str, Any]] = []
    record = TeamRecord()

    target = _normalise_name(team_name)

    sorted_matches = sorted(matches, key=lambda m: (_parse_match_datetime(m) or datetime.min))

    for match in sorted_matches:
        home_team = match.get("home_team", {}).get("home_team_name")
        away_team = match.get("away_team", {}).get("away_team_name")
        home_score = match.get("home_score")
        away_score = match.get("away_score")
        stage = match.get("competition_stage", {}).get("name")
        match_status = match.get("match_status")
        dt = _parse_match_datetime(match)
        date_display = dt.strftime("%Y-%m-%d") if dt else (match.get("match_date") or "?")

        is_home = _normalise_name(home_team) == target
        is_away = _normalise_name(away_team) == target
        if not (is_home or is_away):
            continue

        opponent = away_team if is_home else home_team
        venue = "Home" if is_home else "Away"
        summary = {
            "match_id": match.get("match_id"),
            "date": date_display,
            "opponent": opponent,
            "venue": venue,
            "status": match_status,
            "stage": stage,
            "score": None,
            "result": None,
            "goals_for": None,
            "goals_against": None,
        }

        if home_score is not None and away_score is not None:
            gf = _to_int(home_score if is_home else away_score, default=0)
            ga = _to_int(away_score if is_home else home_score, default=0)
            if gf > ga:
                outcome = "W"
            elif gf < ga:
                outcome = "L"
            else:
                outcome = "D"
            summary.update(
                {
                    "score": f"{home_score}-{away_score}",
                    "result": outcome,
                    "goals_for": gf,
                    "goals_against": ga,
                }
            )
            record = TeamRecord(
                played=record.played + 1,
                won=record.won + (1 if outcome == "W" else 0),
                drawn=record.drawn + (1 if outcome == "D" else 0),
                lost=record.lost + (1 if outcome == "L" else 0),
                goals_for=record.goals_for + gf,
                goals_against=record.goals_against + ga,
            )
            played.append(summary)
        else:
            upcoming.append(summary)

    played.sort(key=lambda item: item["date"], reverse=True)
    upcoming.sort(key=lambda item: item["date"])

    return played, upcoming, record


def _prepare_roster_table(roster: Sequence[Dict[str, Any]], *, limit: int = 40) -> List[Dict[str, Any]]:
    sorted_roster = sorted(
        roster,
        key=lambda row: _to_float(row.get("player_season_minutes") or row.get("minutes_played")),
        reverse=True,
    )
    prepared: List[Dict[str, Any]] = []
    for row in sorted_roster[:limit]:
        prepared.append(
            {
                "player_id": row.get("player_id") or row.get("offline_player_id"),
                "player_name": row.get("player_name"),
                "position": row.get("position"),
                "minutes": _to_int(row.get("player_season_minutes") or row.get("minutes_played")),
                "goals": _to_int(row.get("player_season_goals") or row.get("goals")),
                "assists": _to_int(row.get("player_season_assists") or row.get("assists")),
            }
        )
    return prepared


def _top_performers(roster: Sequence[Dict[str, Any]], *, count: int = 3) -> Dict[str, List[Dict[str, Any]]]:
    top_stats: Dict[str, List[Dict[str, Any]]] = {"goals": [], "assists": [], "minutes": []}
    if not roster:
        return top_stats

    def build(entries: Sequence[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
        filtered = [
            {
                "player_name": row.get("player_name"),
                "value": _to_float(row.get(key)),
                "team_name": row.get("team_name"),
                "position": row.get("position"),
            }
            for row in entries
            if row.get(key) not in (None, "")
        ]
        filtered.sort(key=lambda item: item["value"], reverse=True)
        return [
            {**item, "metric": key}
            for item in filtered[:count]
            if item["value"] > 0
        ]

    roster_list = list(roster)
    top_stats["goals"] = build(roster_list, "player_season_goals")
    top_stats["assists"] = build(roster_list, "player_season_assists")
    top_stats["minutes"] = build(roster_list, "player_season_minutes")
    return top_stats


def _recent_formations(
    team_name: str,
    matches: Sequence[Dict[str, Any]],
    *,
    max_matches: int = 6,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    formations: List[Dict[str, Any]] = []
    if not matches:
        return formations

    client = get_statsbomb_client()
    target = _normalise_name(team_name)
    seen: set[str] = set()

    for match in matches:
        if len(formations) >= max_matches:
            break
        match_id = match.get("match_id")
        if not match_id:
            continue
        try:
            lineups = client.get_lineups(match_id, use_cache=use_cache)
        except Exception:  # pragma: no cover
            continue
        if not isinstance(lineups, list):
            continue
        for entry in lineups:
            entry_team = entry.get("team_name")
            if _normalise_name(entry_team) != target:
                continue
            formation = entry.get("formation") or entry.get("starting_formation")
            if not formation:
                continue
            formation_str = str(formation)
            if formation_str in seen:
                break
            seen.add(formation_str)
            formations.append(
                {
                    "formation": formation_str,
                    "match_id": match_id,
                    "date": match.get("match_date"),
                    "opponent": match.get("opponent"),
                }
            )
            break
    return formations


def _resolve_competition_name(
    competition_id: int,
    *,
    use_cache: bool = True,
) -> Optional[str]:
    try:
        competitions = list_competitions(use_cache=use_cache)
    except Exception:  # pragma: no cover - tolerate network hiccups
        return None
    for competition in competitions:
        if competition.get("competition_id") == competition_id:
            return competition.get("competition_name")
    return None


def load_team_context(
    competition_id: int,
    season_label: str,
    team_name: str,
    *,
    competition_name: Optional[str] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Build an aggregate view of a team's season context.
    Returns a dict suitable for UI display and prompt conditioning.
    """

    context: Dict[str, Any] = {
        "competition_id": competition_id,
        "season_label": season_label,
        "team_name": team_name,
        "season_id": None,
        "competition_name": competition_name,
        "table": [],
        "table_position": None,
        "table_size": 0,
        "team_summary": None,
        "roster_raw": [],
        "roster_table": [],
        "matches_played": [],
        "matches_upcoming": [],
        "record": TeamRecord().to_dict(),
        "next_match": None,
        "recent_result": None,
        "top_stats": {},
        "formations": [],
        "errors": [],
    }

    try:
        season_id = season_id_for_label(competition_id, season_label, use_cache=use_cache)
    except Exception as exc:  # pragma: no cover - network/credential issues
        context["errors"].append(f"Season resolution failed: {exc}")
        season_id = None

    context["season_id"] = season_id

    team_stats: List[Dict[str, Any]] = []
    if season_id is not None:
        try:
            team_stats = fetch_team_season_stats_data(
                competition_id,
                season_id,
                use_cache=use_cache,
            )
        except Exception as exc:  # pragma: no cover - API failures
            context["errors"].append(f"Team season stats unavailable: {exc}")

    if team_stats:
        table = _sort_table(team_stats)
        context["table"] = table
        context["table_size"] = len(table)
        team_row = _find_team_row(team_name, table)
        if team_row:
            context["team_summary"] = team_row
            context["table_position"] = team_row.get("position")
    else:
        context["table"] = []

    try:
        roster = get_competition_players(
            competition_id=competition_id,
            season_label=season_label,
            team_name=team_name,
            metrics=None,
            use_cache=use_cache,
        )
        context["roster_raw"] = roster
        context["roster_table"] = _prepare_roster_table(roster)
        context["top_stats"] = _top_performers(roster)
    except Exception as exc:  # pragma: no cover - API failures
        context["errors"].append(f"Roster lookup failed: {exc}")

    if season_id is not None:
        try:
            matches = list_matches(
                competition_id,
                season_id,
                team_name=team_name,
                use_cache=use_cache,
            )
        except Exception as exc:  # pragma: no cover - API failures
            context["errors"].append(f"Match list unavailable: {exc}")
            matches = []
        played, upcoming, record = _summarise_matches(team_name, matches)
        context["matches_played"] = played
        context["matches_upcoming"] = upcoming
        context["record"] = record.to_dict()
        context["recent_result"] = played[0] if played else None
        context["next_match"] = upcoming[0] if upcoming else None
        context["formations"] = _recent_formations(team_name, played + upcoming, use_cache=use_cache)
    else:
        context["errors"].append("Season ID unavailable; matches not loaded.")

    if not context.get("competition_name"):
        context["competition_name"] = _resolve_competition_name(competition_id, use_cache=use_cache)

    return context


def list_teams_for_season(
    competition_id: int,
    season_label: str,
    *,
    use_cache: bool = True,
) -> List[str]:
    """
    Return sorted team names for a competition season.
    """

    try:
        season_id = season_id_for_label(competition_id, season_label, use_cache=use_cache)
    except Exception as exc:  # pragma: no cover - network/credential issues
        raise RuntimeError(f"Failed to resolve season: {exc}") from exc

    if season_id is None:
        raise RuntimeError("Season identifier not found.")

    rows = fetch_team_season_stats_data(
        competition_id,
        season_id,
        use_cache=use_cache,
    )
    names = {row.get("team_name") for row in rows if row.get("team_name")}
    return sorted(names)


def summarise_context_for_prompt(
    context: Dict[str, Any],
    *,
    user_name: Optional[str] = None,
    competition_name: Optional[str] = None,
) -> str:
    team = context.get("team_name")
    if not team:
        return ""

    season_label = context.get("season_label")
    comp_label = competition_name or f"competition {context.get('competition_id')}"
    record = context.get("record") or {}
    table_position = context.get("table_position")
    table_size = context.get("table_size")
    team_summary = context.get("team_summary") or {}
    points = team_summary.get("team_season_points")
    matches_played = record.get("played")
    won = record.get("won")
    drawn = record.get("drawn")
    lost = record.get("lost")
    goals_for = record.get("goals_for")
    goals_against = record.get("goals_against")
    goal_diff = record.get("goal_difference")
    next_match = context.get("next_match")

    lines: List[str] = []
    if user_name:
        lines.append(f"User '{user_name}' is logged in as a representative of {team}.")
    lines.append(f"Team focus: {team} in {comp_label} ({season_label}).")
    if table_position and table_size:
        table_line = f"Table position: {table_position}/{table_size}"
        if points is not None:
            table_line += f" with {points} points"
        lines.append(table_line + ".")
    if matches_played:
        record_line = (
            f"Season record {won}W-{drawn}D-{lost}L over {matches_played} matches, "
            f"goals {goals_for}-{goals_against} (GD {goal_diff})."
        )
        lines.append(record_line)
    if next_match:
        lines.append(
            f"Next fixture: {next_match.get('date')} vs {next_match.get('opponent')} ({next_match.get('venue')})."
        )

    return "Workspace context:\n" + "\n".join(lines)


_TEAM_CONTEXT_CACHE: Dict[Tuple[int, str, str], Tuple[float, Dict[str, Any]]] = {}
TEAM_CONTEXT_CACHE_TTL = 300.0


def get_team_context_cached(
    competition_id: int,
    season_label: str,
    team_name: str,
    *,
    refresh: bool = False,
    use_cache: bool = True,
) -> Dict[str, Any]:
    key = (
        competition_id,
        _normalise_name(season_label or ""),
        _normalise_name(team_name),
    )
    if use_cache and not refresh:
        cached = _TEAM_CONTEXT_CACHE.get(key)
        if cached and (time() - cached[0]) < TEAM_CONTEXT_CACHE_TTL:
            return cached[1]

    context = load_team_context(
        competition_id,
        season_label,
        team_name,
        use_cache=use_cache,
    )
    _TEAM_CONTEXT_CACHE[key] = (time(), context)
    return context


def clear_team_context_cache() -> None:
    _TEAM_CONTEXT_CACHE.clear()
