"""
High level StatsBomb query helpers optimised for quick reuse.
"""
from __future__ import annotations

import dataclasses
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from ..clients.statsbomb import StatsBombClient
from ..exceptions import APINotFoundError
from .data_fetch import get_statsbomb_client

PitchLocation = Tuple[float, float]

PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0
FINAL_THIRD_X = 80.0
MIDDLE_THIRD_MIN_X = 40.0
PENALTY_AREA_X = 102.0
PENALTY_Y_LOW = 18.0
PENALTY_Y_HIGH = 62.0
HALFSPACE_LEFT_Y = (18.0, 32.0)
HALFSPACE_RIGHT_Y = (48.0, 62.0)
WIDE_LEFT_Y = (0.0, 18.0)
WIDE_RIGHT_Y = (62.0, 80.0)

ScoreState = str

_SEQUENCE_FILTER_FIELDS = {
    "event_types",
    "team_names",
    "opponent_names",
    "player_names",
    "possession_team_names",
    "periods",
    "play_patterns",
    "outcome_names",
    "score_states",
}

_NON_ASCII_REPLACEMENTS = {
    "ß": "ss",
    "ø": "o",
    "Ø": "o",
    "æ": "ae",
    "Æ": "ae",
    "œ": "oe",
    "Œ": "oe",
    "ł": "l",
    "Ł": "l",
    "đ": "d",
    "Đ": "d",
    "ð": "d",
    "Ð": "d",
    "þ": "th",
    "Þ": "th",
    "ı": "i",
    "İ": "i",
    "ŋ": "ng",
    "Ŋ": "ng",
}


def _canonical(value: str) -> str:
    """
    Lowercase, collapse whitespace, and replace diacritics or special characters.
    """
    if not value:
        return ""

    normalised = unicodedata.normalize("NFKD", value)
    cleaned_parts: List[str] = []
    for char in normalised:
        if unicodedata.combining(char):
            continue

        candidate: str | None = char
        if not char.isascii():
            candidate = _NON_ASCII_REPLACEMENTS.get(char)
            if candidate is None:
                name = unicodedata.name(char, "")
                if "LETTER" in name:
                    parts = name.split()
                    try:
                        idx = parts.index("LETTER") + 1
                        candidate = parts[idx]
                    except (ValueError, IndexError):
                        candidate = ""
                else:
                    candidate = ""

        if not candidate:
            continue

        cleaned_parts.append(candidate.lower())

    cleaned = "".join(cleaned_parts)
    return " ".join(cleaned.strip().split())


def _normalise_season_label(label: str) -> str:
    trimmed = label.strip()
    if not trimmed:
        return trimmed
    normalised = trimmed.replace('-', '/').replace('\\', '/')
    match = re.match(r'^(\\d{4})/(\\d{2})$', normalised)
    if match:
        start = int(match.group(1))
        end = int(match.group(2))
        end_full = start // 100 * 100 + end
        if end_full <= start:
            end_full += 100
        return f"{start}/{end_full}"
    match = re.match(r'^(\\d{4})/(\\d{4})$', normalised)
    if match:
        return normalised
    match = re.match(r'^(\\d{4})$', normalised)
    if match:
        start = int(match.group(1))
        return f"{start}/{start + 1}"
    return normalised

POPULAR_COMPETITIONS: List[Dict[str, Any]] = [
    {
        "competition_id": 2,
        "name": "Premier League",
        "aliases": ["premier league", "england premier league", "epl"],
        "season_ids": {
            "2025/2026": 318,
            "2024/2025": 317,
            "2023/2024": 281,
            "2022/2023": 235,
            "2021/2022": 108,
        },
    },
    {
        "competition_id": 11,
        "name": "La Liga",
        "aliases": ["laliga", "la liga", "spanish la liga"],
        "season_ids": {},
    },
    {
        "competition_id": 9,
        "name": "Serie A",
        "aliases": ["serie a", "italy serie a"],
        "season_ids": {},
    },
    {
        "competition_id": 12,
        "name": "Bundesliga",
        "aliases": ["bundesliga", "german bundesliga"],
        "season_ids": {},
    },
    {
        "competition_id": 13,
        "name": "Ligue 1",
        "aliases": ["ligue 1", "french ligue 1"],
        "season_ids": {},
    },
    {
        "competition_id": 16,
        "name": "UEFA Champions League",
        "aliases": ["uefa champions league", "champions league"],
        "season_ids": {},
    },
    {
        "competition_id": 37,
        "name": "Major League Soccer",
        "aliases": ["major league soccer", "mls"],
        "season_ids": {},
    },
    {
        "competition_id": 72,
        "name": "Eredivisie",
        "aliases": ["eredivisie", "dutch eredivisie"],
        "season_ids": {},
    },
    {
        "competition_id": 43,
        "name": "FA Women's Super League",
        "aliases": ["fa women's super league", "wsl"],
        "season_ids": {},
    },
    {
        "competition_id": 46,
        "name": "UEFA Women's Champions League",
        "aliases": ["uefa women's champions league", "women's champions league"],
        "season_ids": {},
    },
]

_season_cache: Dict[Tuple[int, str], int] = {}

_POPULAR_ALIAS_INDEX: Dict[str, int] = {}
_HARDCODED_SEASON_IDS: Dict[Tuple[int, str], int] = {}

for entry in POPULAR_COMPETITIONS:
    comp_id = entry["competition_id"]
    aliases = set(entry.get("aliases", []))
    aliases.add(entry.get("name", ""))
    for alias in aliases:
        canonical_alias = _canonical(alias)
        if canonical_alias:
            _POPULAR_ALIAS_INDEX[canonical_alias] = comp_id
    for season_label, season_id in entry.get("season_ids", {}).items():
        normalised_label = _canonical(_normalise_season_label(season_label))
        _HARDCODED_SEASON_IDS[(comp_id, normalised_label)] = season_id


@dataclass(frozen=True)
class MatchDescriptor:
    """
    Identify a match and optionally provide known metadata.
    """

    match_id: int
    competition_id: Optional[int] = None
    season_id: Optional[int] = None
    match: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class EventFilters:
    """
    Declarative filters applied to match events.
    """

    event_types: Optional[Sequence[str]] = None
    team_names: Optional[Sequence[str]] = None
    opponent_names: Optional[Sequence[str]] = None
    player_names: Optional[Sequence[str]] = None
    possession_team_names: Optional[Sequence[str]] = None
    periods: Optional[Sequence[int]] = None
    minute_range: Optional[Tuple[int, int]] = None
    time_range: Optional[Tuple[float, float]] = None
    score_states: Optional[Sequence[ScoreState]] = None
    play_patterns: Optional[Sequence[str]] = None
    outcome_names: Optional[Sequence[str]] = None
    zone: Optional[str] = None
    location_key: str = "start"
    custom_filter: Optional[Callable[[Dict[str, Any], Dict[str, Any]], bool]] = None


@dataclass(frozen=True)
class EventContext:
    """
    Event enriched with match context for downstream analysis.
    """

    event: Dict[str, Any]
    match: Dict[str, Any]
    home_score: int
    away_score: int
    score_state: ScoreState
    elapsed_seconds: float


@dataclass(frozen=True)
class MatchDataset:
    """
    Bundle of match level data ready for downstream queries.
    """

    descriptor: MatchDescriptor
    match: Dict[str, Any]
    events: List[EventContext]
    lineups: Optional[List[Dict[str, Any]]] = None
    frames: Optional[List[Dict[str, Any]]] = None


@dataclass(frozen=True)
class PlayerEventSummary:
    """
    Aggregate view of player events across matches.
    """

    total: int
    by_match: Dict[int, int]


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _select_columns(row: Dict[str, Any], metrics: Optional[Sequence[str]]) -> Dict[str, Any]:
    if not metrics:
        return row
    return {key: row.get(key) for key in metrics if key in row}


def list_competitions(
    *,
    name: Optional[str] = None,
    country: Optional[str] = None,
    only_with_data: bool = False,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """
    Retrieve competitions with optional filtering by name, country, or data availability.
    """
    client = get_statsbomb_client()
    competitions = client.list_competitions(use_cache=use_cache)
    if name:
        lowered = name.lower()
        competitions = [
            comp
            for comp in competitions
            if lowered in comp.get("competition_name", "").lower()
        ]
    if country:
        lowered = country.lower()
        competitions = [
            comp
            for comp in competitions
            if lowered in (comp.get("country_name") or "").lower()
        ]
    if only_with_data:
        competitions = [comp for comp in competitions if comp.get("match_available")]
    return competitions


def list_seasons(
    competition_id: int,
    *,
    season_name: Optional[str] = None,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """
    Fetch seasons for a competition, optionally filtered by season name.
    """
    client = get_statsbomb_client()
    seasons = client.list_seasons(competition_id, use_cache=use_cache)
    if season_name:
        lowered = season_name.lower()
        seasons = [
            season
            for season in seasons
            if lowered in season.get("season_name", "").lower()
        ]
    return seasons


def list_matches(
    competition_id: int,
    season_id: int,
    *,
    team_name: Optional[str] = None,
    opponent_name: Optional[str] = None,
    match_status: Optional[Sequence[str]] = None,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """
    Retrieve matches for a season with optional filters on teams or match status.
    """
    client = get_statsbomb_client()
    try:
        matches = client.list_matches(competition_id, season_id, use_cache=use_cache)
    except APINotFoundError:
        return []

    if team_name:
        matches = [
            match
            for match in matches
            if _team_matches(match, team_name, home=True)
            or _team_matches(match, team_name, home=False)
        ]
    if opponent_name:
        matches = [
            match
            for match in matches
            if _team_matches(match, opponent_name, home=True)
            or _team_matches(match, opponent_name, home=False)
        ]
    if match_status:
        statuses = {status.lower() for status in _ensure_sequence(match_status)}
        matches = [
            match
            for match in matches
            if match.get("match_status", "").lower() in statuses
        ]
    return matches


def find_matches_for_team(
    team_name: str,
    *,
    season_name: Optional[str] = None,
    competition_name: Optional[str] = None,
    opponent_name: Optional[str] = None,
    country: Optional[str] = None,
    competition_ids: Optional[Sequence[int]] = None,
    match_status: Optional[Sequence[str]] = None,
    use_cache: bool = True,
) -> List[MatchDescriptor]:
    """
    Locate matches for a team across competitions and seasons.
    """

    competitions = list_competitions(
        name=competition_name,
        country=country,
        only_with_data=False,
        use_cache=use_cache,
    )
    if competition_ids:
        desired = set(competition_ids)
        competitions = [
            comp for comp in competitions if comp["competition_id"] in desired
        ]

    descriptors: List[MatchDescriptor] = []
    for comp in competitions:
        if season_name and comp.get("season_name") != season_name:
            continue
        comp_id = comp["competition_id"]
        season_id = comp["season_id"]
        matches = list_matches(
            comp_id,
            season_id,
            team_name=team_name,
            opponent_name=opponent_name,
            match_status=match_status,
            use_cache=use_cache,
        )
        for match in matches:
            descriptors.append(
                MatchDescriptor(
                    match_id=match["match_id"],
                    competition_id=comp_id,
                    season_id=season_id,
                    match=match,
                )
            )
    return descriptors


def fetch_match_dataset(
    descriptor: MatchDescriptor,
    *,
    filters: Optional[EventFilters] = None,
    include_lineups: bool = False,
    include_frames: bool = False,
    use_cache: bool = True,
    client: Optional[StatsBombClient] = None,
) -> MatchDataset:
    """
    Fetch match metadata, events, and optional extras in one call.
    """
    statsbomb = client or get_statsbomb_client()
    match = _resolve_match_metadata(descriptor, use_cache=use_cache)
    events = statsbomb.get_events(descriptor.match_id, use_cache=use_cache)
    filtered = apply_filters(events, match, filters)

    lineups = (
        statsbomb.get_lineups(descriptor.match_id, use_cache=use_cache)
        if include_lineups
        else None
    )
    frames = (
        statsbomb.get_360_frames(descriptor.match_id, use_cache=use_cache)
        if include_frames
        else None
    )
    return MatchDataset(
        descriptor=MatchDescriptor(
            match_id=descriptor.match_id,
            competition_id=descriptor.competition_id,
            season_id=descriptor.season_id,
            match=match,
        ),
        match=match,
        events=filtered,
        lineups=lineups,
        frames=frames,
    )


def fetch_team_events(
    competition_id: int,
    season_ids: Sequence[int],
    *,
    team_name: str,
    opponent_name: Optional[str] = None,
    filters: Optional[EventFilters] = None,
    limit: Optional[int] = None,
    include_lineups: bool = False,
    include_frames: bool = False,
    use_cache: bool = True,
) -> Dict[int, MatchDataset]:
    """
    Collect datasets for every match a team plays across multiple seasons.
    """
    statsbomb = get_statsbomb_client()
    results: Dict[int, MatchDataset] = {}
    collected = 0
    for season_id in season_ids:
        matches = list_matches(
            competition_id,
            season_id,
            team_name=team_name,
            opponent_name=opponent_name,
            use_cache=use_cache,
        )
        for match in matches:
            descriptor = MatchDescriptor(
                match_id=match["match_id"],
                competition_id=competition_id,
                season_id=season_id,
                match=match,
            )
            dataset = fetch_match_dataset(
                descriptor,
                filters=filters,
                include_lineups=include_lineups,
                include_frames=include_frames,
                use_cache=use_cache,
                client=statsbomb,
            )
            results[descriptor.match_id] = dataset
            collected += 1
            if limit is not None and collected >= limit:
                return results
    return results


def resolve_competition_id(name: str) -> Optional[int]:
    """Resolve a competition alias to an ID using the built-in index."""

    return _POPULAR_ALIAS_INDEX.get(_canonical(name))


def season_id_for_label(
    competition_id: int,
    season_name: str,
    *,
    use_cache: bool = True,
) -> Optional[int]:
    """Resolve StatsBomb season id for a human-readable label."""

    normalised_label = _normalise_season_label(season_name)
    canonical_label = _canonical(normalised_label)
    key = (competition_id, canonical_label)
    if key in _HARDCODED_SEASON_IDS:
        return _HARDCODED_SEASON_IDS[key]
    if use_cache and key in _season_cache:
        return _season_cache[key]

    seasons = list_seasons(competition_id, use_cache=use_cache)
    for season in seasons:
        if _canonical(_normalise_season_label(season.get("season_name", ""))) == canonical_label:
            season_id = season["season_id"]
            _season_cache[key] = season_id
            _HARDCODED_SEASON_IDS.setdefault(key, season_id)
            return season_id
    return None


def get_player_season_summary(
    *,
    player_name: str,
    season_label: str,
    competition_name: Optional[str] = None,
    competition_id: Optional[int] = None,
    metrics: Optional[Sequence[str]] = None,
    min_minutes: float = 0.0,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Return a summary dict for a player's season across a competition."""

    if competition_id is None:
        if competition_name is None:
            competition_id = 2  # Premier League default
        else:
            competition_id = resolve_competition_id(competition_name) or competition_id
    if competition_id is None:
        raise ValueError("Competition could not be resolved. Provide competition_id explicitly.")

    season_id = season_id_for_label(competition_id, season_label, use_cache=use_cache)
    if season_id is None:
        raise ValueError(
            f"No season_id found for label '{season_label}' in competition {competition_id}."
        )

    records = fetch_player_season_stats_data(
        competition_id,
        season_id,
        player_names=[player_name],
        min_minutes=min_minutes,
        metrics=metrics,
        use_cache=use_cache,
    )
    if not records:
        raise ValueError(
            f"No records returned for player '{player_name}' in season '{season_label}'."
        )
    return records[0]


def get_team_season_summary(
    *,
    team_name: str,
    season_label: str,
    competition_id: int,
    metrics: Optional[Sequence[str]] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Return a summary dict for a team's season."""

    season_id = season_id_for_label(competition_id, season_label, use_cache=use_cache)
    if season_id is None:
        raise ValueError(
            f"No season_id found for label '{season_label}' in competition {competition_id}."
        )

    rows = fetch_team_season_stats_data(
        competition_id,
        season_id,
        metrics=metrics,
        use_cache=use_cache,
    )
    for row in rows:
        if _canonical(row.get("team_name", "")) == _canonical(team_name):
            return row
    raise ValueError(
        f"No record returned for team '{team_name}' in season '{season_label}'."
    )


def get_player_multi_season_summary(
    *,
    player_name: str,
    season_labels: Sequence[str],
    competition_id: int,
    metrics: Optional[Sequence[str]] = None,
    min_minutes: float = 0.0,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """Retrieve records for multiple seasons of the same competition."""

    summaries: List[Dict[str, Any]] = []
    for label in season_labels:
        summary = get_player_season_summary(
            player_name=player_name,
            season_label=label,
            competition_id=competition_id,
            metrics=metrics,
            min_minutes=min_minutes,
            use_cache=use_cache,
        )
        summaries.append(summary)
    return summaries


def get_players_season_summary(
    *,
    player_names: Sequence[str],
    season_label: str,
    competition_id: int,
    metrics: Optional[Sequence[str]] = None,
    min_minutes: float = 0.0,
    use_cache: bool = True,
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Return summary records for multiple players in the same competition season."""

    season_id = season_id_for_label(competition_id, season_label, use_cache=use_cache)
    if season_id is None:
        raise ValueError(
            f"No season_id found for label '{season_label}' in competition {competition_id}."
        )

    rows = fetch_player_season_stats_data(
        competition_id,
        season_id,
        player_names=player_names,
        min_minutes=min_minutes,
        metrics=metrics,
        use_cache=use_cache,
    )
    if not rows or len(rows) < len(player_names):
        rows = fetch_player_season_stats_data(
            competition_id,
            season_id,
            player_names=None,
            min_minutes=min_minutes,
            metrics=metrics,
            use_cache=use_cache,
        )

    summaries: Dict[str, Dict[str, Any]] = {}
    lookup_names = {_canonical(name): name for name in player_names}

    for row in rows:
        player_label = row.get("player_name", "")
        canonical_row = _canonical(player_label)
        row_tokens = set(canonical_row.split())
        for canonical_query, original in lookup_names.items():
            if (
                canonical_query == canonical_row
                or canonical_query in canonical_row
                or canonical_row in canonical_query
            ):
                summaries[original] = row
                break
            query_tokens = set(canonical_query.split())
            if query_tokens & row_tokens:
                summaries[original] = row
                break

    missing = [name for name in player_names if name not in summaries]
    return summaries, missing


def fetch_player_season_stats_data(
    competition_id: int,
    season_id: int,
    *,
    team_name: Optional[str] = None,
    player_names: Optional[Sequence[str]] = None,
    min_minutes: Optional[float] = None,
    sort_by: Optional[str] = None,
    descending: bool = True,
    top_n: Optional[int] = None,
    metrics: Optional[Sequence[str]] = None,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """
    Retrieve player season aggregates with optional filtering and sorting.
    """
    client = get_statsbomb_client()
    rows = client.get_player_season_stats(
        competition_id,
        season_id,
        use_cache=use_cache,
    )
    filtered: List[Dict[str, Any]] = []
    selected_players: List[Tuple[str, set[str]]] = []
    for name in player_names or []:
        canonical_name = _canonical(name)
        if canonical_name:
            selected_players.append((canonical_name, set(canonical_name.split())))

    target_team = _canonical(team_name) if team_name else None
    for row in rows:
        row_team = _canonical(row.get("team_name", ""))
        if target_team and row_team != target_team:
            continue
        row_player = _canonical(row.get("player_name", ""))
        if selected_players:
            row_tokens = set(row_player.split())
            if not any(
                canonical == row_player
                or canonical in row_player
                or row_player in canonical
                or (tokens and row_tokens and tokens & row_tokens)
                for canonical, tokens in selected_players
            ):
                continue
        if min_minutes is not None and _to_float(row.get("player_season_minutes")) < float(min_minutes):
            continue
        filtered.append(_select_columns(row, metrics))

    if sort_by:
        filtered.sort(key=lambda item: _to_float(item.get(sort_by)), reverse=descending)
    if top_n is not None:
        filtered = filtered[:top_n]
    return filtered


def fetch_team_season_stats_data(
    competition_id: int,
    season_id: int,
    *,
    sort_by: Optional[str] = None,
    descending: bool = True,
    top_n: Optional[int] = None,
    metrics: Optional[Sequence[str]] = None,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """
    Retrieve team season aggregates with optional sorting.
    """
    client = get_statsbomb_client()
    rows = client.get_team_season_stats(
        competition_id,
        season_id,
        use_cache=use_cache,
    )
    processed = [_select_columns(row, metrics) for row in rows]
    if sort_by:
        processed.sort(key=lambda item: _to_float(item.get(sort_by)), reverse=descending)
    if top_n is not None:
        processed = processed[:top_n]
    return processed


def fetch_player_match_stats_data(
    match_id: int,
    *,
    team_name: Optional[str] = None,
    sort_by: Optional[str] = None,
    descending: bool = True,
    top_n: Optional[int] = None,
    metrics: Optional[Sequence[str]] = None,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """
    Retrieve player match stats for a given match.
    """
    client = get_statsbomb_client()
    rows = client.get_player_match_stats(match_id, use_cache=use_cache)
    filtered: List[Dict[str, Any]] = []
    target_team = team_name.lower() if team_name else None
    for row in rows:
        if target_team and row.get("team_name", "").lower() != target_team:
            continue
        filtered.append(_select_columns(row, metrics))
    if sort_by:
        filtered.sort(key=lambda item: _to_float(item.get(sort_by)), reverse=descending)
    if top_n is not None:
        filtered = filtered[:top_n]
    return filtered


def fetch_player_events_for_matches(
    match_descriptors: Sequence[MatchDescriptor],
    *,
    player_name: str,
    team_name: Optional[str] = None,
    opponent_name: Optional[str] = None,
    event_types: Optional[Sequence[str]] = None,
    filters: Optional[EventFilters] = None,
    include_lineups: bool = False,
    include_frames: bool = False,
    use_cache: bool = True,
    client: Optional[StatsBombClient] = None,
) -> Dict[int, MatchDataset]:
    """
    Fetch filtered match datasets for a specific player across matches.
    """
    if not match_descriptors:
        return {}
    statsbomb = client or get_statsbomb_client()
    augmented = _augment_filters(
        filters,
        player_names=[player_name],
        event_types=event_types or ["Pass"],
    )
    if team_name:
        augmented = _augment_filters(augmented, team_names=[team_name])
    if opponent_name:
        augmented = _augment_filters(augmented, opponent_names=[opponent_name])

    datasets: Dict[int, MatchDataset] = {}
    for descriptor in match_descriptors:
        dataset = fetch_match_dataset(
            descriptor,
            filters=augmented,
            include_lineups=include_lineups,
            include_frames=include_frames,
            use_cache=use_cache,
            client=statsbomb,
        )
        datasets[descriptor.match_id] = dataset
    return datasets


def count_player_passes_by_body_part(
    match_descriptors: Sequence[MatchDescriptor],
    *,
    player_name: str,
    body_part: str,
    team_name: Optional[str] = None,
    opponent_name: Optional[str] = None,
    filters: Optional[EventFilters] = None,
    use_cache: bool = True,
) -> PlayerEventSummary:
    """
    Count passes by a player with a given body part across matches.
    """
    datasets = fetch_player_events_for_matches(
        match_descriptors,
        player_name=player_name,
        team_name=team_name,
        opponent_name=opponent_name,
        event_types=["Pass"],
        filters=filters,
        use_cache=use_cache,
    )
    by_match: Dict[int, int] = {}
    for match_id, dataset in datasets.items():
        count = sum(
            1
            for ctx in dataset.events
            if _is_pass_by_player(ctx.event, player_name, team_name)
            and _pass_body_part(ctx.event) == body_part
        )
        if count:
            by_match[match_id] = count
        else:
            by_match.setdefault(match_id, 0)
    total = sum(by_match.values())
    return PlayerEventSummary(total=total, by_match=by_match)


def apply_filters(
    events: Sequence[Dict[str, Any]],
    match: Dict[str, Any],
    filters: Optional[EventFilters] = None,
) -> List[EventContext]:
    """
    Filter events with contextual awareness (game state, location zones, etc).
    """
    if filters is None:
        filters = EventFilters()
    compiled = _compile_filters(filters)
    home_team = match["home_team"]["home_team_name"]
    away_team = match["away_team"]["away_team_name"]
    scores = {home_team: 0, away_team: 0}
    filtered: List[EventContext] = []

    for event in events:
        context = {
            "home_team": home_team,
            "away_team": away_team,
            "home_score": scores[home_team],
            "away_score": scores[away_team],
            "match": match,
        }
        if _event_matches(event, compiled, context):
            filtered.append(
                EventContext(
                    event=event,
                    match=match,
                    home_score=scores[home_team],
                    away_score=scores[away_team],
                    score_state=_score_state(event, context),
                    elapsed_seconds=_elapsed_seconds(event),
                )
            )
        _update_scores(event, scores, home_team, away_team)
    return filtered


def _augment_filters(
    filters: Optional[EventFilters], **updates: Any
) -> EventFilters:
    base = filters or EventFilters()
    data = {
        field.name: getattr(base, field.name) for field in dataclasses.fields(EventFilters)
    }
    for key, value in updates.items():
        if value is None:
            continue
        if key in _SEQUENCE_FILTER_FIELDS:
            existing = data.get(key)
            addition = tuple(_ensure_sequence(value))
            if existing:
                existing_seq = tuple(_ensure_sequence(existing))
                merged = []
                for item in existing_seq + addition:
                    if item not in merged:
                        merged.append(item)
                data[key] = tuple(merged)
            else:
                data[key] = addition
        else:
            data[key] = value
    return EventFilters(**data)


def _compile_filters(filters: EventFilters) -> Dict[str, Any]:
    compiled: Dict[str, Any] = {}
    for key in (
        "event_types",
        "team_names",
        "opponent_names",
        "player_names",
        "possession_team_names",
        "play_patterns",
        "outcome_names",
        "score_states",
        "periods",
    ):
        value = getattr(filters, key)
        if value:
            compiled[key] = {item.lower() for item in _ensure_sequence(value)}
    compiled["minute_range"] = filters.minute_range
    compiled["time_range"] = filters.time_range
    compiled["zone"] = filters.zone.lower() if filters.zone else None
    compiled["location_key"] = filters.location_key
    compiled["custom_filter"] = filters.custom_filter

    if compiled.get("score_states"):
        compiled["score_states"] = {
            _canonical_score_state(state) for state in compiled["score_states"]
        }
    return compiled


def _event_matches(
    event: Dict[str, Any],
    filters: Dict[str, Any],
    context: Dict[str, Any],
) -> bool:
    if not filters:
        return True

    if filters.get("event_types"):
        event_type = event.get("type", {}).get("name", "").lower()
        if event_type not in filters["event_types"]:
            return False

    if filters.get("team_names"):
        team_name = event.get("team", {}).get("name", "").lower()
        if team_name not in filters["team_names"]:
            return False

    if filters.get("opponent_names"):
        team_name = event.get("team", {}).get("name", "")
        opponent = _opponent_name(team_name, context["home_team"], context["away_team"])
        if opponent.lower() not in filters["opponent_names"]:
            return False

    if filters.get("player_names"):
        player_name = event.get("player", {}).get("name", "").lower()
        if player_name not in filters["player_names"]:
            return False

    if filters.get("possession_team_names"):
        possession = event.get("possession_team", {}).get("name", "").lower()
        if possession not in filters["possession_team_names"]:
            return False

    if filters.get("periods") and event.get("period") not in filters["periods"]:
        return False

    minute_range = filters.get("minute_range")
    if minute_range:
        minute = event.get("minute")
        if minute is None or minute < minute_range[0] or minute > minute_range[1]:
            return False

    time_range = filters.get("time_range")
    if time_range:
        elapsed = _elapsed_seconds(event)
        if elapsed is None or elapsed < time_range[0] or elapsed > time_range[1]:
            return False

    if filters.get("play_patterns"):
        pattern = event.get("play_pattern", {}).get("name", "").lower()
        if pattern not in filters["play_patterns"]:
            return False

    if filters.get("outcome_names"):
        outcome = _event_outcome(event)
        if outcome.lower() not in filters["outcome_names"]:
            return False

    if filters.get("score_states"):
        score_state = _score_state(event, context)
        if score_state not in filters["score_states"]:
            return False

    zone = filters.get("zone")
    if zone:
        location = _event_location(event, filters.get("location_key", "start"))
        if not _location_in_zone(
            location,
            zone,
            event,
            context["home_team"],
            context["away_team"],
        ):
            return False

    custom = filters.get("custom_filter")
    if custom and not custom(event, context):
        return False

    return True


def _event_location(event: Dict[str, Any], location_key: str) -> Optional[PitchLocation]:
    if location_key == "start":
        return _as_location(event.get("location"))
    if location_key == "end":
        for key in ("pass", "carry", "shot", "clearance"):
            if key in event:
                loc = event[key].get("end_location") or event[key].get("end_location")
                if loc:
                    return _as_location(loc)
        return None
    if "." in location_key:
        head, tail = location_key.split(".", 1)
        nested = event.get(head, {})
        if isinstance(nested, dict):
            return _as_location(nested.get(tail))
        return None
    return _as_location(event.get(location_key))


def _as_location(value: Any) -> Optional[PitchLocation]:
    if not value or not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None


def _location_in_zone(
    location: Optional[PitchLocation],
    zone: str,
    event: Dict[str, Any],
    home_team: str,
    away_team: str,
) -> bool:
    if location is None:
        return False
    attacking_direction = _attacking_direction(
        event.get("team", {}).get("name"),
        event.get("period"),
        home_team,
        away_team,
    )
    rel_x, rel_y = _relative_coordinates(location, attacking_direction)
    zone = zone.lower()

    if zone == "final_third":
        return rel_x >= FINAL_THIRD_X
    if zone == "middle_third":
        return MIDDLE_THIRD_MIN_X <= rel_x < FINAL_THIRD_X
    if zone == "defensive_third":
        return rel_x < MIDDLE_THIRD_MIN_X
    if zone == "penalty_area":
        return rel_x >= PENALTY_AREA_X and PENALTY_Y_LOW <= rel_y <= PENALTY_Y_HIGH
    if zone == "halfspace_left":
        return HALFSPACE_LEFT_Y[0] <= rel_y < HALFSPACE_LEFT_Y[1]
    if zone == "halfspace_right":
        return HALFSPACE_RIGHT_Y[0] <= rel_y < HALFSPACE_RIGHT_Y[1]
    if zone == "wide_left":
        return WIDE_LEFT_Y[0] <= rel_y < WIDE_LEFT_Y[1]
    if zone == "wide_right":
        return WIDE_RIGHT_Y[0] <= rel_y < WIDE_RIGHT_Y[1]
    if zone == "central":
        return HALFSPACE_LEFT_Y[1] <= rel_y < HALFSPACE_RIGHT_Y[0]
    return False


def _relative_coordinates(
    location: PitchLocation,
    attacking_direction: str,
) -> PitchLocation:
    x, y = location
    if attacking_direction == "right":
        return x, y
    return PITCH_LENGTH - x, PITCH_WIDTH - y


def _attacking_direction(
    team_name: Optional[str],
    period: Optional[int],
    home_team: str,
    away_team: str,
) -> str:
    if team_name is None:
        return "right"
    if period in (2, 4, 6):
        return "left" if team_name == home_team else "right"
    return "right" if team_name == home_team else "left"


def _is_pass_by_player(
    event: Dict[str, Any],
    player_name: str,
    team_name: Optional[str] = None,
) -> bool:
    if event.get("type", {}).get("name") != "Pass":
        return False
    if event.get("player", {}).get("name") != player_name:
        return False
    if team_name and event.get("team", {}).get("name") != team_name:
        return False
    return True


def _pass_body_part(event: Dict[str, Any]) -> str:
    data = event.get("pass")
    if not isinstance(data, dict):
        return ""
    body = data.get("body_part")
    if isinstance(body, dict):
        return body.get("name", "") or ""
    return ""


def _score_state(event: Dict[str, Any], context: Dict[str, Any]) -> ScoreState:
    team_name = event.get("team", {}).get("name")
    home_score = context["home_score"]
    away_score = context["away_score"]
    if home_score == away_score:
        return "level"
    if team_name == context["home_team"]:
        return "leading" if home_score > away_score else "trailing"
    if team_name == context["away_team"]:
        return "leading" if away_score > home_score else "trailing"
    return "level"


def _canonical_score_state(state: str) -> ScoreState:
    mapping = {
        "leading": "leading",
        "ahead": "leading",
        "winning": "leading",
        "trailing": "trailing",
        "behind": "trailing",
        "losing": "trailing",
        "level": "level",
        "tied": "level",
        "draw": "level",
    }
    return mapping.get(state, state)


def _elapsed_seconds(event: Dict[str, Any]) -> float:
    minute = event.get("minute", 0)
    second = event.get("second", 0.0)
    return float(minute) * 60.0 + float(second or 0.0)


def _event_outcome(event: Dict[str, Any]) -> str:
    for key in ("shot", "pass", "carry", "duel", "dribble"):
        data = event.get(key)
        if isinstance(data, dict):
            outcome = data.get("outcome")
            if isinstance(outcome, dict) and outcome.get("name"):
                return outcome["name"]
    return event.get("type", {}).get("name", "")


def _update_scores(
    event: Dict[str, Any],
    scores: Dict[str, int],
    home_team: str,
    away_team: str,
) -> None:
    scoring_team = _goal_team(event)
    if scoring_team is None:
        return
    if scoring_team == home_team:
        scores[home_team] += 1
    elif scoring_team == away_team:
        scores[away_team] += 1


def _goal_team(event: Dict[str, Any]) -> Optional[str]:
    event_type = event.get("type", {}).get("name")
    if event_type == "Shot":
        shot = event.get("shot", {})
        outcome = shot.get("outcome", {}).get("name")
        if outcome == "Goal":
            return event.get("team", {}).get("name")
    if event_type == "Own Goal For":
        return event.get("team", {}).get("name")
    return None


def _resolve_match_metadata(
    descriptor: MatchDescriptor,
    *,
    use_cache: bool = True,
) -> Dict[str, Any]:
    if descriptor.match:
        return descriptor.match
    if descriptor.competition_id is None or descriptor.season_id is None:
        raise ValueError(
            "competition_id and season_id must be provided when match metadata is absent"
        )
    lookup = _match_index(descriptor.competition_id, descriptor.season_id, use_cache)
    match = lookup.get(descriptor.match_id)
    if match is None:
        raise KeyError(
            f"Match {descriptor.match_id} not found in competition {descriptor.competition_id} "
            f"season {descriptor.season_id}"
        )
    return match


@lru_cache(maxsize=64)
def _match_index(
    competition_id: int,
    season_id: int,
    use_cache: bool,
) -> Dict[int, Dict[str, Any]]:
    client = get_statsbomb_client()
    try:
        matches = client.list_matches(competition_id, season_id, use_cache=use_cache)
    except APINotFoundError:
        return {}
    return {match["match_id"]: match for match in matches}


def _team_matches(match: Dict[str, Any], name: str, *, home: bool) -> bool:
    lookup = match["home_team"] if home else match["away_team"]
    key = "home_team_name" if home else "away_team_name"
    return lookup.get(key, "").lower() == name.lower()


def _format_rows(
    rows: List[Dict[str, object]],
    fields: Optional[List[str]] = None,
    limit: int = 5,
) -> str:
    if not rows:
        return ""
    preview_fields = fields or sorted(rows[0].keys())
    lines: List[str] = []
    for row in rows[: max(limit, 0)]:
        parts: List[str] = []
        for field in preview_fields:
            if field in row and row[field] not in (None, ""):
                parts.append(f"{field}={row[field]}")
        if parts:
            lines.append("- " + ", ".join(parts))
    return "\n".join(lines)


def _ensure_sequence(value: Iterable[str] | str) -> Sequence[str]:
    if isinstance(value, str):
        return [value]
    return list(value)


def _opponent_name(team_name: str, home_team: str, away_team: str) -> str:
    if team_name == home_team:
        return away_team
    return home_team
