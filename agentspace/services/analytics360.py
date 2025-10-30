"""
Utilities for building 360-degree analytics derived from StatsBomb freeze-frame data.
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .data_fetch import (
    fetch_statsbomb_360,
    fetch_statsbomb_events,
    fetch_statsbomb_matches,
    get_statsbomb_client,
)
from .team_context import season_id_for_label

Number = float | int

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Team360Query:
    competition_id: int
    season_id: int
    team_id: int
    max_matches: int = 6
    use_cache: bool = True


@dataclass(frozen=True)
class Player360Query:
    competition_id: int
    season_id: int
    team_id: int
    player_id: int
    max_matches: int = 6
    use_cache: bool = True


@dataclass(frozen=True)
class MetricResult:
    key: str
    label: str
    value: Number
    unit: Optional[str] = None
    sample_size: int = 0
    notes: Optional[str] = None


@dataclass
class _TeamAnalyticsDataset:
    team_id: int
    matches: List[Dict[str, Any]]
    events_by_match: Dict[int, List[Dict[str, Any]]]
    frames_by_event: Dict[str, List[Dict[str, Any]]]


@dataclass
class _PlayerAnalyticsDataset:
    team: _TeamAnalyticsDataset
    player_id: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise(value: Optional[Sequence[Number]]) -> Optional[Tuple[float, float]]:
    if not value or len(value) < 2:
        return None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None


def _team_id_from_match(team_name: str, match: Dict[str, Any]) -> Optional[int]:
    home = match.get("home_team") or {}
    away = match.get("away_team") or {}
    if (home.get("home_team_name") or "").lower() == team_name.lower():
        return home.get("home_team_id")
    if (away.get("away_team_name") or "").lower() == team_name.lower():
        return away.get("away_team_id")
    return None


def _collect_matches(query: Team360Query) -> List[Dict[str, Any]]:
    matches = fetch_statsbomb_matches(query.competition_id, query.season_id)
    relevant: List[Dict[str, Any]] = []
    for match in matches:
        home_id = (match.get("home_team") or {}).get("home_team_id")
        away_id = (match.get("away_team") or {}).get("away_team_id")
        if query.team_id in {home_id, away_id}:
            relevant.append(match)
        if len(relevant) >= query.max_matches:
            break
    return relevant


def _collect_events(
    query: Team360Query,
    matches: Sequence[Dict[str, Any]],
) -> Tuple[Dict[int, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    events_by_match: Dict[int, List[Dict[str, Any]]] = {}
    frames_by_event: Dict[str, List[Dict[str, Any]]] = {}
    for match in matches:
        match_id = match.get("match_id")
        if not match_id:
            continue
        events = fetch_statsbomb_events(match_id)
        events_by_match[match_id] = events
        frames = fetch_statsbomb_360(match_id)
        for frame in frames:
            event_uuid = frame.get("event_uuid")
            if not event_uuid:
                continue
            frames_by_event.setdefault(event_uuid, []).append(frame)
    return events_by_match, frames_by_event


def _ensure_team_and_player_ids(
    competition_id: int,
    season_id: int,
    team_name: Optional[str],
    team_id: Optional[int],
    player_name: Optional[str],
    player_id: Optional[int],
) -> Tuple[int, Optional[int]]:
    resolved_team_id = team_id
    if resolved_team_id is None and team_name:
        matches = fetch_statsbomb_matches(competition_id, season_id)
        for match in matches:
            tid = _team_id_from_match(team_name, match)
            if tid:
                resolved_team_id = tid
                break
    resolved_player_id = player_id
    if resolved_player_id is None and player_name and resolved_team_id:
        roster = get_statsbomb_client().get_player_season_stats(
            competition_id,
            season_id,
            use_cache=True,
        )
        for row in roster:
            if (
                row.get("team_id") == resolved_team_id
                and (row.get("player_name") or "").lower() == player_name.lower()
            ):
                resolved_player_id = row.get("player_id")
                break
    if resolved_team_id is None:
        raise ValueError("team_id is required when team_name cannot be resolved.")
    return resolved_team_id, resolved_player_id


# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------


def _orient_location(
    raw: Optional[Sequence[Number]],
    *,
    team_side: Optional[str],
    pitch_length: float = 120.0,
    pitch_width: float = 80.0,
) -> Optional[Tuple[float, float]]:
    loc = _normalise(raw)
    if loc is None:
        return None
    x, y = loc
    if team_side == "away":
        x = pitch_length - x
        y = pitch_width - y
    return x, y


def _determine_team_side(match: Dict[str, Any], team_id: int) -> str:
    home = match.get("home_team") or {}
    if home.get("home_team_id") == team_id:
        return "home"
    return "away"


def _compute_low_block_pressures(dataset: _TeamAnalyticsDataset) -> MetricResult:
    count = 0
    total_events = 0
    for match in dataset.matches:
        match_id = match.get("match_id")
        if match_id is None:
            continue
        events = dataset.events_by_match.get(match_id, [])
        for event in events:
            team = (event.get("team") or {}).get("id")
            if team != dataset.team_id:
                continue
            event_type = (event.get("type") or {}).get("name") or ""
            if event_type.lower() != "pressure":
                continue
            loc = _orient_location(event.get("location"), team_side=_determine_team_side(match, dataset.team_id))
            total_events += 1
            if not loc:
                continue
            # Use oriented y-axis so defensive third corresponds to y >= 53.3
            if loc[1] >= 53.3:
                count += 1
    return MetricResult(
        key="low_block_pressures",
        label="Low-block pressure events",
        value=count,
        unit="events",
        sample_size=total_events,
        notes="Pressure events with y >= 53.3 (defensive third) across analysed matches.",
    )


def _compute_average_defensive_line(dataset: _TeamAnalyticsDataset) -> MetricResult:
    y_positions: List[float] = []
    for match in dataset.matches:
        match_id = match.get("match_id")
        if match_id is None:
            continue
        side = _determine_team_side(match, dataset.team_id)
        events = dataset.events_by_match.get(match_id, [])
        for event in events:
            team = (event.get("team") or {}).get("id")
            if team != dataset.team_id:
                continue
            event_uuid = event.get("id") or event.get("event_uuid")
            if not event_uuid:
                continue
            frames = dataset.frames_by_event.get(event_uuid) or []
            for frame in frames:
                players = frame.get("players") or []
                for player in players:
                    if player.get("teammate") and not player.get("keeper"):
                        loc = _orient_location(player.get("location"), team_side=side)
                        if loc:
                            y_positions.append(loc[1])
    if not y_positions:
        return MetricResult(
            key="avg_defensive_line",
            label="Average defensive line height",
            value=0.0,
            unit="y_coordinate",
            sample_size=0,
            notes="360 freeze-frames unavailable or missing defender coordinates.",
        )
    avg_y = sum(y_positions) / len(y_positions)
    return MetricResult(
        key="avg_defensive_line",
        label="Average defensive line height",
        value=round(avg_y, 2),
        unit="y_coordinate",
        sample_size=len(y_positions),
        notes="Mean y-coordinate of teammates (non-keeper) across freeze-frames after orientation.",
    )


def _compute_carrier_pressure_distance(dataset: _PlayerAnalyticsDataset) -> MetricResult:
    distances: List[float] = []
    for match in dataset.team.matches:
        match_id = match.get("match_id")
        if match_id is None:
            continue
        events = dataset.team.events_by_match.get(match_id, [])
        for event in events:
            if (event.get("player") or {}).get("id") != dataset.player_id:
                continue
            event_uuid = event.get("id") or event.get("event_uuid")
            if not event_uuid:
                continue
            frames = dataset.team.frames_by_event.get(event_uuid) or []
            for frame in frames:
                for player in frame.get("players") or []:
                    if not player.get("teammate") and player.get("nearest_defender"):
                        dist = player.get("distance")
                        if dist is not None:
                            try:
                                distances.append(float(dist))
                            except (TypeError, ValueError):
                                continue
    if not distances:
        return MetricResult(
            key="avg_defender_distance",
            label="Average nearest defender distance",
            value=0.0,
            unit="m",
            sample_size=0,
            notes="No 360-distance data available for player.",
        )
    avg_dist = sum(distances) / len(distances)

    return MetricResult(
        key="avg_defender_distance",
        label="Average nearest defender distance",
        value=round(avg_dist, 2),
        unit="m",
        sample_size=len(distances),
    )


def _compute_box_touches(dataset: _PlayerAnalyticsDataset) -> MetricResult:
    touches = 0
    total = 0
    for match_id, events in dataset.team.events_by_match.items():
        for event in events:
            if (event.get("player") or {}).get("id") != dataset.player_id:
                continue
            event_type = (event.get("type") or {}).get("name") or ""
            if event_type.lower() not in {"touch", "ball receipt"}:
                continue
            loc = _normalise(event.get("location"))
            total += 1
            if not loc:
                continue
            # StatsBomb pitch 120 x 80; attacking box approx x >= 102, y between 18 and 62.
            if loc[0] >= 102 and 18 <= loc[1] <= 62:
                touches += 1
    return MetricResult(
        key="box_touches",
        label="Touches in penalty box",
        value=touches,
        unit="touches",
        sample_size=total,
    )


TeamMetricFn = Callable[[_TeamAnalyticsDataset], MetricResult]
PlayerMetricFn = Callable[[_PlayerAnalyticsDataset], MetricResult]

TEAM_METRICS: List[TeamMetricFn] = [
    _compute_low_block_pressures,
    _compute_average_defensive_line,
]

PLAYER_METRICS: List[PlayerMetricFn] = [
    _compute_carrier_pressure_distance,
    _compute_box_touches,
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_TEAM_CACHE: Dict[Tuple[int, int, int, int], Tuple[float, Dict[str, Any]]] = {}
_PLAYER_CACHE: Dict[Tuple[int, int, int, int, int], Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL = 300.0


def collect_team_360_metrics(
    competition_id: int,
    season_label: str,
    team_id: Optional[int] = None,
    team_name: Optional[str] = None,
    *,
    max_matches: int = 6,
    refresh: bool = False,
) -> Dict[str, Any]:
    season_id = season_id_for_label(competition_id, season_label)
    if season_id is None:
        raise ValueError(f"Unable to resolve season_id for {season_label}.")

    resolved_team_id, _ = _ensure_team_and_player_ids(
        competition_id,
        season_id,
        team_name,
        team_id,
        None,
        None,
    )
    cache_key = (competition_id, season_id, resolved_team_id, max_matches)
    if not refresh:
        cached = _TEAM_CACHE.get(cache_key)
        if cached and (time.time() - cached[0]) < _CACHE_TTL:
            return cached[1]

    query = Team360Query(
        competition_id=competition_id,
        season_id=season_id,
        team_id=resolved_team_id,
        max_matches=max_matches,
    )
    matches = _collect_matches(query)
    events_by_match, frames_by_event = _collect_events(query, matches)

    dataset = _TeamAnalyticsDataset(
        team_id=resolved_team_id,
        matches=matches,
        events_by_match=events_by_match,
        frames_by_event=frames_by_event,
    )
    metrics = [metric(dataset) for metric in TEAM_METRICS]
    payload = {
        "team_id": resolved_team_id,
        "competition_id": competition_id,
        "season_id": season_id,
        "season_label": season_label,
        "match_count": len(matches),
        "metrics": [metric.__dict__ for metric in metrics],
    }
    _TEAM_CACHE[cache_key] = (time.time(), payload)
    return payload


def collect_player_360_metrics(
    competition_id: int,
    season_label: str,
    team_id: Optional[int] = None,
    team_name: Optional[str] = None,
    player_id: Optional[int] = None,
    player_name: Optional[str] = None,
    *,
    max_matches: int = 6,
    refresh: bool = False,
) -> Dict[str, Any]:
    season_id = season_id_for_label(competition_id, season_label)
    if season_id is None:
        raise ValueError(f"Unable to resolve season_id for {season_label}.")

    resolved_team_id, resolved_player_id = _ensure_team_and_player_ids(
        competition_id,
        season_id,
        team_name,
        team_id,
        player_name,
        player_id,
    )
    if resolved_player_id is None:
        raise ValueError("player_id is required when player_name cannot be resolved.")

    cache_key = (competition_id, season_id, resolved_team_id, resolved_player_id, max_matches)
    if not refresh:
        cached = _PLAYER_CACHE.get(cache_key)
        if cached and (time.time() - cached[0]) < _CACHE_TTL:
            return cached[1]

    team_query = Team360Query(
        competition_id=competition_id,
        season_id=season_id,
        team_id=resolved_team_id,
        max_matches=max_matches,
    )
    matches = _collect_matches(team_query)
    events_by_match, frames_by_event = _collect_events(team_query, matches)
    team_dataset = _TeamAnalyticsDataset(
        team_id=resolved_team_id,
        matches=matches,
        events_by_match=events_by_match,
        frames_by_event=frames_by_event,
    )
    player_dataset = _PlayerAnalyticsDataset(
        team=team_dataset,
        player_id=resolved_player_id,
    )
    metrics = [metric(player_dataset) for metric in PLAYER_METRICS]
    payload = {
        "team_id": resolved_team_id,
        "player_id": resolved_player_id,
        "competition_id": competition_id,
        "season_id": season_id,
        "season_label": season_label,
        "match_count": len(matches),
        "metrics": [metric.__dict__ for metric in metrics],
    }
    _PLAYER_CACHE[cache_key] = (time.time(), payload)
    return payload


def clear_analytics360_cache() -> None:
    _TEAM_CACHE.clear()
    _PLAYER_CACHE.clear()
