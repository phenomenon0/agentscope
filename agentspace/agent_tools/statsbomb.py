"""
Agentscope toolkit integration for StatsBomb data helpers.
"""

from typing import Any, Dict, List, Optional, Tuple

from agentscope.message import TextBlock
from agentscope.tool import Toolkit, ToolResponse
import agentscope

from ..services.statsbomb_tools import (
    EventFilters,
    MatchDataset,
    MatchDescriptor,
    PlayerEventSummary,
    POPULAR_COMPETITIONS,
    count_player_passes_by_body_part,
    fetch_match_dataset,
    fetch_player_match_stats_data,
    fetch_player_season_stats_data,
    fetch_team_season_stats_data,
    find_matches_for_team,
    get_player_multi_season_summary,
    get_player_season_summary,
    get_players_season_summary,
    get_team_season_summary,
    list_competitions,
    list_seasons,
    _canonical,
    resolve_competition_id,
    season_id_for_label,
)

PLAYER_SEASON_DEFAULT_FIELDS = [
    "player_name",
    "team_name",
    "player_season_minutes",
    "player_season_goals_90",
    "player_season_xa_90",
    "player_season_np_xg_90",
]

PLAYER_SEASON_SUMMARY_MAP = [
    ("player_season_minutes", "Minutes"),
    ("player_season_goals", "Total goals"),
    ("player_season_goals_90", "Goals/90"),
    ("player_season_assists", "Total assists"),
    ("player_season_assists_90", "Assists/90"),
    ("player_season_np_xg", "Non-pen xG"),
    ("player_season_np_xg_90", "Non-pen xG/90"),
    ("player_season_xa", "xA"),
    ("player_season_xa_90", "xA/90"),
    ("player_season_shots_90", "Shots/90"),
    ("player_season_key_passes_90", "Key passes/90"),
    ("player_season_pressures_90", "Pressures/90"),
]

TEAM_SEASON_DEFAULT_FIELDS = [
    "team_name",
    "team_season_goals",
    "team_season_xg",
    "team_season_xga",
    "team_season_points",
]

TEAM_SEASON_SUMMARY_MAP = [
    ("team_season_points", "Points"),
    ("team_season_matches", "Matches"),
    ("team_season_goals", "Goals"),
    ("team_season_goals_against", "Goals conceded"),
    ("team_season_xg", "xG"),
    ("team_season_xga", "xGA"),
]

PLAYER_MATCH_DEFAULT_FIELDS = [
    "player_name",
    "team_name",
    "player_match_minutes",
    "player_match_goals",
    "player_match_xg",
    "player_match_assists",
]

PLAYER_MATCH_SUMMARY_MAP = [
    ("player_match_minutes", "Minutes"),
    ("player_match_goals", "Goals"),
    ("player_match_assists", "Assists"),
    ("player_match_xg", "xG"),
    ("player_match_shots", "Shots"),
]

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _summarise_metrics(record: Dict[str, Any], mapping: List[Tuple[str, str]]) -> str:
    lines = []
    for key, label in mapping:
        value = record.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, float):
            value = f"{value:.2f}"
        lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def _error_response(text: str, metadata: Dict[str, Any]) -> ToolResponse:
    return ToolResponse(content=[TextBlock(type="text", text=text)], metadata=metadata)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register_statsbomb_tools(
    toolkit: Optional[Toolkit] = None,
    *,
    group_name: str = "statsbomb",
    activate: bool = True,
) -> Toolkit:
    """
    Register StatsBomb data tooling with an Agentscope toolkit.

    Args:
        toolkit: Optional existing toolkit to extend. A new Toolkit is created
            when omitted.
        group_name: Tool group label used inside the toolkit.
        activate: Whether to activate the tool group immediately.

    Returns:
        The toolkit instance with the StatsBomb tools registered.
    """
    toolkit = toolkit or Toolkit()

    try:
        toolkit.create_tool_group(
            group_name,
            description="StatsBomb data access and analytics helpers.",
            active=activate,
            notes=(
                "These tools operate on authenticated StatsBomb Data API "
                "endpoints. Provide clear filters (team names, season labels, "
                "competition names, match ids) to limit network calls. "
                "Prefer calling `list_team_matches` before detailed queries "
                "to capture competition/season identifiers."
            ),
        )
    except ValueError:
        # Group already exists; that's fine.
        pass

    toolkit.register_tool_function(
        list_competitions_tool,
        group_name=group_name,
        func_description="List competitions available via the StatsBomb Data API.",
    )
    toolkit.register_tool_function(
        list_seasons_tool,
        group_name=group_name,
        func_description="List seasons for a specific competition.",
    )
    toolkit.register_tool_function(
        list_team_matches,
        group_name=group_name,
        func_description="Find StatsBomb matches for a team with optional "
        "season, competition, and opponent filters.",
    )
    toolkit.register_tool_function(
        count_player_passes_by_body_part_tool,
        group_name=group_name,
        func_description="Count a player's passes using a specific body part "
        "across the selected matches.",
    )
    toolkit.register_tool_function(
        fetch_match_events,
        group_name=group_name,
        func_description="Fetch filtered match events (and optional lineups "
        "or 360 frames) for a specific StatsBomb match.",
    )
    toolkit.register_tool_function(
        fetch_player_season_aggregates,
        group_name=group_name,
        func_description="Retrieve player season aggregates with optional sorting and filtering.",
    )
    toolkit.register_tool_function(
        fetch_team_season_aggregates,
        group_name=group_name,
        func_description="Retrieve team season aggregates with optional sorting.",
    )
    toolkit.register_tool_function(
        fetch_player_match_aggregates,
        group_name=group_name,
        func_description="Retrieve per-player match statistics for a single match.",
    )
    toolkit.register_tool_function(
        player_season_summary_tool,
        group_name=group_name,
        func_description="Quick lookup for a player's season summary in a major competition.",
    )
    toolkit.register_tool_function(
        team_season_summary_tool,
        group_name=group_name,
        func_description="Quick lookup for a team's season summary in a major competition.",
    )
    toolkit.register_tool_function(
        player_multi_season_summary_tool,
        group_name=group_name,
        func_description="Retrieve player summaries across multiple seasons in one call.",
    )
    toolkit.register_tool_function(
        compare_player_season_summaries_tool,
        group_name=group_name,
        func_description="Compare multiple players in the same competition season.",
    )
    return toolkit


def init_session_with_statsbomb_tools(
    *,
    project: Optional[str] = None,
    name: Optional[str] = None,
    logging_path: Optional[str] = None,
    logging_level: str = "INFO",
    studio_url: Optional[str] = None,
    tracing_url: Optional[str] = None,
    toolkit: Optional[Toolkit] = None,
    group_name: str = "statsbomb",
    activate: bool = True,
) -> Toolkit:
    """Initialise Agentscope and register StatsBomb tools.

    This helper combines :func:`agentscope.init` with
    :func:`register_statsbomb_tools`, returning the prepared toolkit for use
    in agent sessions.
    """

    agentscope.init(
        project=project,
        name=name,
        logging_path=logging_path,
        logging_level=logging_level,
        studio_url=studio_url,
        tracing_url=tracing_url,
    )
    return register_statsbomb_tools(
        toolkit=toolkit,
        group_name=group_name,
        activate=activate,
    )


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def list_competitions_tool(
    name: Optional[str] = None,
    country: Optional[str] = None,
    only_with_data: bool = False,
    use_cache: bool = True,
) -> ToolResponse:
    """List StatsBomb competitions."""

    if name:
        resolved = resolve_competition_id(name)
        if resolved is not None and not country and not only_with_data:
            entry = next((item for item in POPULAR_COMPETITIONS if item["competition_id"] == resolved), None)
            if entry:
                season_rows = [
                    {"season_label": label, "season_id": sid}
                    for label, sid in entry.get("season_ids", {}).items()
                ]
                preview = _format_rows(
                    season_rows,
                    fields=["season_label", "season_id"],
                    limit=len(season_rows),
                )
                lines = [
                    f"Known competition: {entry.get('name', name)} (competition_id={resolved}).",
                    "Known season ids:",
                    preview or "- Season IDs not cached; call list_seasons_tool if needed.",
                ]
                metadata = {
                    "competition_id": resolved,
                    "aliases": entry.get("aliases", []),
                    "season_ids": entry.get("season_ids", {}),
                }
                return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=metadata)

    competitions = list_competitions(
        name=name,
        country=country,
        only_with_data=only_with_data,
        use_cache=use_cache,
    )
    preview_rows = competitions
    prioritized = [row for row in competitions if row.get("match_available")]
    if prioritized:
        preview_rows = prioritized
    preview = _format_rows(
        preview_rows,
        fields=["competition_id", "competition_name", "season_id", "season_name", "match_available"],
    )
    lines = [
        f"Found {len(competitions)} competition(s).",
        "Sample (competition_id, competition_name, season_id, season_name, match_available):",
        preview or "- None",
        "Full results available in metadata['competitions'].",
    ]
    metadata = {"competitions": competitions}
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=metadata)


def list_seasons_tool(
    competition_id: int,
    season_name: Optional[str] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """List seasons for a competition."""

    try:
        seasons = list_seasons(competition_id, season_name=season_name, use_cache=use_cache)
    except Exception as exc:  # pylint: disable=broad-except
        message = f"Failed to fetch seasons for competition {competition_id}: {exc}"
        return ToolResponse(
            content=[TextBlock(type="text", text=message)],
            metadata={"competition_id": competition_id, "error": str(exc)},
        )

    preview_rows = seasons
    prioritized = [row for row in seasons if row.get("match_available")]
    if prioritized:
        preview_rows = prioritized
    preview = _format_rows(
        preview_rows,
        fields=["season_id", "season_name", "match_updated", "match_available"],
    )
    lines = [
        f"Found {len(seasons)} season(s) for competition {competition_id}.",
        "Sample (season_id, season_name, match_updated, match_available):",
        preview or "- None",
        "Full results available in metadata['seasons'].",
    ]
    metadata = {"competition_id": competition_id, "seasons": seasons}
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=metadata)


def list_team_matches(
    team_name: str,
    season_name: Optional[str] = None,
    competition_name: Optional[str] = None,
    opponent_name: Optional[str] = None,
    country: Optional[str] = None,
    competition_ids: Optional[List[int]] = None,
    match_status: Optional[List[str]] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """
    List StatsBomb matches for a team.

    Args:
        team_name: Name of the team to search for (case insensitive).
        season_name: Optional season label (for example, ``"2024/2025"``).
        competition_name: Optional competition name filter.
        opponent_name: Restrict to matches played against this opponent.
        country: Restrict competitions to a specific country.
        competition_ids: Optional list of numeric competition identifiers.
        match_status: Optional list of match status labels, such as
            ``["played"]`` or ``["scheduled"]``.
        use_cache: Whether to honour the local response cache.

    Returns:
        ToolResponse containing a summary message and metadata with match
        descriptors.
    """
    descriptors = find_matches_for_team(
        team_name=team_name,
        season_name=season_name,
        competition_name=competition_name,
        opponent_name=opponent_name,
        country=country,
        competition_ids=competition_ids,
        match_status=match_status,
        use_cache=use_cache,
    )
    payload = [_descriptor_to_dict(descriptor) for descriptor in descriptors]
    preview_rows = sorted(
        payload,
        key=lambda row: row.get("match_date") or "",
        reverse=True,
    )
    preview = _format_rows(
        preview_rows,
        fields=[
            "match_id",
            "match_date",
            "home_team",
            "away_team",
            "competition_name",
            "season_name",
        ],
    )
    summary_lines = [
        f"Found {len(payload)} match(es) for {team_name}"
        f"{' vs ' + opponent_name if opponent_name else ''}"
        f"{' in ' + season_name if season_name else ''}.",
        "Sample (match_id, date, home, away, competition, season):",
        preview or "- None",
        "Full results available in metadata['matches'].",
    ]
    metadata = {"matches": payload}
    return ToolResponse(
        content=[TextBlock(type="text", text="\n".join(summary_lines))],
        metadata=metadata,
    )


def count_player_passes_by_body_part_tool(
    player_name: str,
    body_part: str,
    *,
    team_name: Optional[str] = None,
    opponent_name: Optional[str] = None,
    season_name: Optional[str] = None,
    competition_name: Optional[str] = None,
    country: Optional[str] = None,
    competition_ids: Optional[List[int]] = None,
    match_ids: Optional[List[int]] = None,
    match_competition_id: Optional[int] = None,
    match_season_id: Optional[int] = None,
    periods: Optional[List[int]] = None,
    minute_range: Optional[List[int]] = None,
    time_range: Optional[List[float]] = None,
    score_states: Optional[List[str]] = None,
    zone: Optional[str] = None,
    location_key: str = "start",
    use_cache: bool = True,
) -> ToolResponse:
    """
    Count passes played with a specific body part by a player.

    Args:
        player_name: Player to analyse.
        body_part: Body part label (for example, ``"Left Foot"``).
        team_name: Optional team name filter when locating matches.
        opponent_name: Optional opponent filter.
        season_name: Optional season label constraint.
        competition_name: Optional competition name filter.
        country: Optional country filter for competitions.
        competition_ids: Explicit numeric competition identifiers to search.
        match_ids: Optional explicit match identifiers. When provided,
            ``match_competition_id`` and ``match_season_id`` are used to
            recover metadata.
        match_competition_id: Competition identifier for ``match_ids``.
        match_season_id: Season identifier for ``match_ids``.
        periods: Optional list of period numbers (1-4) to include.
        minute_range: Two-element range (inclusive) restricting event minutes.
        time_range: Two-element range (inclusive) restricting elapsed seconds.
        score_states: Optional list of score state labels (``"leading"``,
            ``"trailing"``, ``"level"``).
        zone: Optional pitch zone filter (``"final_third"``, ``"penalty_area"``,
            ``"halfspace_left"``, etc).
        location_key: Location attribute to evaluate when applying the ``zone``
            filter. Defaults to ``"start"``.
        use_cache: Whether to honour the response cache.

    Returns:
        ToolResponse with aggregate totals per match in the metadata.
    """
    descriptors = _collect_descriptors(
        match_ids=match_ids or [],
        match_competition_id=match_competition_id,
        match_season_id=match_season_id,
        team_name=team_name,
        opponent_name=opponent_name,
        season_name=season_name,
        competition_name=competition_name,
        country=country,
        competition_ids=competition_ids,
        use_cache=use_cache,
    )
    if not descriptors:
        raise ValueError(
            "No matches identified. Provide match_ids or sufficient filters."
        )

    filters = EventFilters(
        periods=list(periods) if periods else None,
        minute_range=_normalize_range(minute_range),
        time_range=_normalize_range(time_range),
        score_states=list(score_states) if score_states else None,
        zone=zone,
        location_key=location_key,
    )

    summary = count_player_passes_by_body_part(
        descriptors,
        player_name=player_name,
        body_part=body_part,
        team_name=team_name,
        opponent_name=opponent_name,
        filters=filters,
        use_cache=use_cache,
    )
    text = _summarise_player_passes(
        summary=summary,
        player_name=player_name,
        body_part=body_part,
    ) + " Metadata 'totals' contains per-match counts."
    metadata = {
        "player": player_name,
        "body_part": body_part,
        "totals": summary.by_match,
        "total_passes": summary.total,
    }
    return ToolResponse(
        content=[TextBlock(type="text", text=text)],
        metadata=metadata,
    )


def fetch_match_events(
    match_id: int,
    competition_id: int,
    season_id: int,
    *,
    team_name: Optional[str] = None,
    opponent_name: Optional[str] = None,
    event_types: Optional[List[str]] = None,
    player_names: Optional[List[str]] = None,
    periods: Optional[List[int]] = None,
    minute_range: Optional[List[int]] = None,
    time_range: Optional[List[float]] = None,
    score_states: Optional[List[str]] = None,
    zone: Optional[str] = None,
    location_key: str = "start",
    include_lineups: bool = False,
    include_frames: bool = False,
    limit: int = 25,
    use_cache: bool = True,
) -> ToolResponse:
    """
    Retrieve match events with optional filters applied.

    Args:
        match_id: StatsBomb match identifier.
        competition_id: Competition identifier containing the match.
        season_id: Season identifier containing the match.
        team_name: Optional team filter.
        opponent_name: Optional opponent filter.
        event_types: Optional list of event type names.
        player_names: Optional list of player names.
        periods: Optional list of period numbers.
        minute_range: Two-element (inclusive) minute range filter.
        time_range: Two-element (inclusive) elapsed-seconds range filter.
        score_states: Optional list of score state labels.
        zone: Optional pitch zone filter.
        location_key: Location attribute considered when applying ``zone``.
        include_lineups: Whether to include the lineup payload.
        include_frames: Whether to include 360 freeze-frame data.
        limit: Maximum number of events to include in the textual preview.
        use_cache: Honour the local cache when available.

    Returns:
        ToolResponse with a textual summary and structured metadata containing
        the filtered events.
    """
    filters = EventFilters(
        event_types=list(event_types) if event_types else None,
        team_names=[team_name] if team_name else None,
        opponent_names=[opponent_name] if opponent_name else None,
        player_names=list(player_names) if player_names else None,
        periods=list(periods) if periods else None,
        minute_range=_normalize_range(minute_range),
        time_range=_normalize_range(time_range),
        score_states=list(score_states) if score_states else None,
        zone=zone,
        location_key=location_key,
    )
    descriptor = MatchDescriptor(
        match_id=match_id,
        competition_id=competition_id,
        season_id=season_id,
    )
    dataset = fetch_match_dataset(
        descriptor,
        filters=filters,
        include_lineups=include_lineups,
        include_frames=include_frames,
        use_cache=use_cache,
    )

    preview_rows = _preview_events(dataset, limit)
    preview = _format_rows(
        preview_rows,
        fields=["event_id", "type", "team", "player", "minute", "second", "score_state"],
    )
    lines = [
        f"Retrieved {len(dataset.events)} event(s) for match {match_id}.",
        "Preview (event_id, type, team, player, minute, second, score_state):",
        preview or "- None",
        "Lineups and raw events available in metadata.",
    ]
    metadata = {
        "match": _descriptor_to_dict(dataset.descriptor),
        "preview_events": preview_rows,
        "lineups": dataset.lineups if include_lineups else None,
        "frames": dataset.frames if include_frames else None,
    }
    return ToolResponse(
        content=[TextBlock(type="text", text="\n".join(lines))],
        metadata=metadata,
    )


def fetch_player_season_aggregates(
    competition_id: int,
    season_id: int,
    *,
    team_name: Optional[str] = None,
    player_names: Optional[List[str]] = None,
    min_minutes: Optional[float] = None,
    sort_by: Optional[str] = None,
    descending: bool = True,
    top_n: Optional[int] = 10,
    metrics: Optional[List[str]] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """Fetch player season aggregates for a competition season."""

    records = fetch_player_season_stats_data(
        competition_id,
        season_id,
        team_name=team_name,
        player_names=player_names,
        min_minutes=min_minutes,
        sort_by=sort_by,
        descending=descending,
        top_n=top_n,
        metrics=metrics,
        use_cache=use_cache,
    )
    preview_limit = min(len(records), 5) if records else 5
    field_list = list(metrics) if metrics else sorted(records[0].keys())
    text_preview = _format_rows(records, fields=field_list, limit=preview_limit)
    summary_lines = _summarise_metrics(records[0], PLAYER_SEASON_SUMMARY_MAP)
    lines = [
        f"Retrieved {len(records)} player season record(s) for competition {competition_id} season {season_id}.",
        "Key metrics:",
        summary_lines or "- N/A",
        "Preview of first records:",
        text_preview or "- None",
        "Full dataset available in metadata['records'].",
    ]
    metadata = {
        "competition_id": competition_id,
        "season_id": season_id,
        "records": records,
        "sort_by": sort_by,
    }
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=metadata)


def fetch_team_season_aggregates(
    competition_id: int,
    season_id: int,
    *,
    sort_by: Optional[str] = None,
    descending: bool = True,
    top_n: Optional[int] = 10,
    metrics: Optional[List[str]] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """Fetch team season aggregates for a competition season."""

    records = fetch_team_season_stats_data(
        competition_id,
        season_id,
        sort_by=sort_by,
        descending=descending,
        top_n=top_n,
        metrics=metrics,
        use_cache=use_cache,
    )
    preview_limit = min(len(records), 5) if records else 5
    field_list = list(metrics) if metrics else sorted(records[0].keys())
    text_preview = _format_rows(records, fields=field_list, limit=preview_limit)
    summary_lines = _summarise_metrics(records[0], TEAM_SEASON_SUMMARY_MAP)
    lines = [
        f"Retrieved {len(records)} team season record(s) for competition {competition_id} season {season_id}.",
        "Key metrics:",
        summary_lines or "- N/A",
        "Preview of first records:",
        text_preview or "- None",
        "Full dataset available in metadata['records'].",
    ]
    metadata = {
        "competition_id": competition_id,
        "season_id": season_id,
        "records": records,
        "sort_by": sort_by,
    }
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=metadata)


def fetch_player_match_aggregates(
    match_id: int,
    *,
    team_name: Optional[str] = None,
    sort_by: Optional[str] = None,
    descending: bool = True,
    top_n: Optional[int] = 10,
    metrics: Optional[List[str]] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """Fetch per-player match aggregates for a single match."""

    rows = fetch_player_match_stats_data(
        match_id,
        team_name=team_name,
        sort_by=sort_by,
        descending=descending,
        top_n=top_n,
        metrics=metrics,
        use_cache=use_cache,
    )
    preview_limit = min(len(rows), 5) if rows else 5
    field_list = list(metrics) if metrics else sorted(rows[0].keys())
    text_preview = _format_rows(rows, fields=field_list, limit=preview_limit)
    summary_lines = _summarise_metrics(rows[0], PLAYER_MATCH_SUMMARY_MAP) if rows else ""
    lines = [
        f"Retrieved {len(rows)} player match record(s) for match {match_id}.",
        "Key metrics (first record):",
        summary_lines or "- N/A",
        "Preview:",
        text_preview or "- None",
        "Full dataset available in metadata['records'].",
    ]
    metadata = {
        "match_id": match_id,
        "team_name": team_name,
        "records": rows,
        "sort_by": sort_by,
    }
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=metadata)


def player_season_summary_tool(
    player_name: str,
    season_label: str,
    *,
    competition: str = "Premier League",
    competition_id: Optional[int] = None,
    team_name: Optional[str] = None,
    metrics: Optional[List[str]] = None,
    min_minutes: float = 0.0,
    use_cache: bool = True,
) -> ToolResponse:
    """Quick helper returning a player's season summary."""

    resolved_competition_id = competition_id or resolve_competition_id(competition)
    if resolved_competition_id is None:
        return _error_response(
            f"Competition '{competition}' could not be resolved.",
            {"competition": competition, "season_label": season_label},
        )

    try:
        summary = get_player_season_summary(
            player_name=player_name,
            season_label=season_label,
            competition_id=resolved_competition_id,
            metrics=metrics,
            min_minutes=min_minutes,
            use_cache=use_cache,
        )
    except ValueError as exc:
        return _error_response(
            f"No data found for {player_name} in {competition} {season_label}. Detail: {exc}",
            {
                "player": player_name,
                "competition_id": resolved_competition_id,
                "season_label": season_label,
                "error": str(exc),
            },
        )

    if team_name and _canonical(summary.get("team_name", "")) != _canonical(team_name):
        return _error_response(
            f"Player {player_name} belongs to {summary.get('team_name')}, not {team_name}.",
            {
                "player": player_name,
                "team": summary.get("team_name"),
                "expected_team": team_name,
                "competition_id": resolved_competition_id,
                "season_label": season_label,
            },
        )

    display_fields = metrics or sorted(summary.keys())
    preview = _format_rows([summary], fields=display_fields, limit=1)
    summary_lines = _summarise_metrics(summary, PLAYER_SEASON_SUMMARY_MAP)
    text = (
        f"Season summary for {summary.get('player_name')} in {season_label}"
        f" ({summary.get('team_name')}).\nKey metrics:\n{summary_lines or '- N/A'}\n"
        f"Raw fields:\n{preview}"
    )
    metadata = {
        "player": summary.get("player_name"),
        "team": summary.get("team_name"),
        "competition_id": resolved_competition_id,
        "season_label": season_label,
        "record": summary,
    }
    return ToolResponse(content=[TextBlock(type="text", text=text)], metadata=metadata)


def team_season_summary_tool(
    team_name: str,
    season_label: str,
    *,
    competition: str = "Premier League",
    competition_id: Optional[int] = None,
    metrics: Optional[List[str]] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """Return a quick summary for a team season."""

    resolved_competition_id = competition_id or resolve_competition_id(competition)
    if resolved_competition_id is None:
        return _error_response(
            f"Competition '{competition}' could not be resolved.",
            {"team": team_name, "competition": competition, "season_label": season_label},
        )

    try:
        summary = get_team_season_summary(
            team_name=team_name,
            season_label=season_label,
            competition_id=resolved_competition_id,
            metrics=metrics,
            use_cache=use_cache,
        )
    except ValueError as exc:
        return _error_response(
            f"No data found for {team_name} in {competition} {season_label}. Detail: {exc}",
            {
                "team": team_name,
                "competition_id": resolved_competition_id,
                "season_label": season_label,
                "error": str(exc),
            },
        )

    field_list = list(metrics) if metrics else sorted(summary.keys())
    preview = _format_rows([summary], fields=field_list, limit=1)
    summary_lines = _summarise_metrics(summary, TEAM_SEASON_SUMMARY_MAP)
    text = (
        f"Season summary for {summary.get('team_name')} in {season_label}.\n"
        f"Key metrics:\n{summary_lines or '- N/A'}\nRaw fields:\n{preview}"
    )
    metadata = {
        "team": summary.get("team_name"),
        "competition_id": resolved_competition_id,
        "season_label": season_label,
        "record": summary,
    }
    return ToolResponse(content=[TextBlock(type="text", text=text)], metadata=metadata)


def player_multi_season_summary_tool(
    player_name: str,
    season_labels: List[str],
    *,
    competition: str = "Premier League",
    competition_id: Optional[int] = None,
    competition_ids: Optional[List[int]] = None,
    competitions: Optional[List[str]] = None,
    metrics: Optional[List[str]] = None,
    min_minutes: float = 0.0,
    use_cache: bool = True,
) -> ToolResponse:
    """Return summaries across multiple seasons for a player."""

    if competition_ids and competitions:
        raise ValueError("Specify either competition_ids or competitions, not both.")

    resolved_ids: List[int] = []
    if competition_ids:
        resolved_ids = competition_ids
    elif competitions:
        for comp_name in competitions:
            comp_id = resolve_competition_id(comp_name)
            if comp_id is None:
                return _error_response(
                    f"Competition '{comp_name}' not recognised.",
                    {"competition": comp_name},
                )
            resolved_ids.append(comp_id)
    else:
        comp_id = competition_id or resolve_competition_id(competition)
        if comp_id is None:
            return _error_response(
                "Competition not recognised. Provide explicit competition info.",
                {"competition": competition, "season_labels": season_labels},
            )
        resolved_ids = [comp_id] * len(season_labels)

    if len(resolved_ids) != len(season_labels):
        return _error_response(
            "Number of competition ids must match number of season labels.",
            {"competition_ids": resolved_ids, "season_labels": season_labels},
        )

    summaries: List[Dict[str, Any]] = []
    for label, comp_id in zip(season_labels, resolved_ids):
        try:
            summary = get_player_season_summary(
                player_name=player_name,
                season_label=label,
                competition_id=comp_id,
                metrics=metrics,
                min_minutes=min_minutes,
                use_cache=use_cache,
            )
            summaries.append(summary)
        except ValueError as exc:
            return _error_response(
                f"No data for {player_name} in season {label}. Detail: {exc}",
                {
                    "player": player_name,
                    "season_label": label,
                    "competition_id": comp_id,
                    "error": str(exc),
                },
            )

    field_list = list(metrics) if metrics else sorted(summaries[0].keys())
    preview = _format_rows(summaries, fields=field_list, limit=len(season_labels))
    summary_sections = []
    for record, label in zip(summaries, season_labels):
        metrics_text = _summarise_metrics(record, PLAYER_SEASON_SUMMARY_MAP)
        summary_sections.append(
            f"{label} ({record.get('team_name', 'N/A')}):\n{metrics_text or '- N/A'}"
        )
    text = (
        f"Summaries for {player_name} across seasons {', '.join(season_labels)}.\n"
        + "\n".join(summary_sections)
        + f"\nRaw fields:\n{preview}"
    )
    metadata = {
        "player": player_name,
        "competition_ids": resolved_ids,
        "season_labels": season_labels,
        "records": summaries,
    }
    return ToolResponse(content=[TextBlock(type="text", text=text)], metadata=metadata)


def compare_player_season_summaries_tool(
    player_names: List[str],
    season_label: str,
    *,
    competition: str = "Premier League",
    competition_id: Optional[int] = None,
    metrics: Optional[List[str]] = None,
    min_minutes: float = 0.0,
    use_cache: bool = True,
) -> ToolResponse:
    """Compare multiple players within the same competition season."""

    if len(player_names) < 2:
        raise ValueError("Provide at least two player names to compare.")

    resolved_competition_id = competition_id or resolve_competition_id(competition)
    if resolved_competition_id is None:
        return _error_response(
            "Competition not recognised. Provide explicit competition info.",
            {"player_names": player_names, "season_label": season_label},
        )

    try:
        summaries, missing = get_players_season_summary(
            player_names=player_names,
            season_label=season_label,
            competition_id=resolved_competition_id,
            metrics=metrics,
            min_minutes=min_minutes,
            use_cache=use_cache,
        )
    except ValueError as exc:
        return _error_response(
            f"Unable to compare players in {competition} {season_label}. Detail: {exc}",
            {
                "competition_id": resolved_competition_id,
                "season_label": season_label,
                "player_names": player_names,
                "error": str(exc),
            },
        )

    missing = [name for name in missing if name not in summaries]
    if not summaries:
        return _error_response(
            f"No comparison data available for {', '.join(player_names)} in {competition} {season_label}.",
            {
                "competition_id": resolved_competition_id,
                "season_label": season_label,
                "player_names": player_names,
                "missing": missing,
            },
        )

    available_names = [name for name in player_names if name in summaries]
    field_list = list(metrics) if metrics else sorted(next(iter(summaries.values())).keys())
    preview_rows = [summaries[name] for name in available_names]
    preview = _format_rows(preview_rows, fields=field_list, limit=len(preview_rows))

    summary_sections = []
    for name in available_names:
        record = summaries[name]
        metrics_text = _summarise_metrics(record, PLAYER_SEASON_SUMMARY_MAP)
        summary_sections.append(
            f"{name} ({record.get('team_name', 'N/A')}):\n{metrics_text or '- N/A'}"
        )

    text = (
        f"Comparison for {', '.join(available_names)} in {season_label}.\n"
        + "\n".join(summary_sections)
        + f"\nRaw fields:\n{preview}"
    )
    if missing:
        text += f"\nMissing data for: {', '.join(missing)}."
    metadata = {
        "competition_id": resolved_competition_id,
        "season_label": season_label,
        "records": summaries,
        "missing": missing,
    }
    return ToolResponse(content=[TextBlock(type="text", text=text)], metadata=metadata)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_descriptors(
    *,
    match_ids: List[int],
    match_competition_id: Optional[int],
    match_season_id: Optional[int],
    team_name: Optional[str],
    opponent_name: Optional[str],
    season_name: Optional[str],
    competition_name: Optional[str],
    country: Optional[str],
    competition_ids: Optional[List[int]],
    use_cache: bool,
) -> List[MatchDescriptor]:
    descriptors: Dict[int, MatchDescriptor] = {}

    if match_ids:
        if match_competition_id is None or match_season_id is None:
            raise ValueError(
                "match_competition_id and match_season_id are required when "
                "using match_ids."
            )
        for match_id in match_ids:
            descriptors[match_id] = MatchDescriptor(
                match_id=match_id,
                competition_id=match_competition_id,
                season_id=match_season_id,
            )

    if team_name:
        for descriptor in find_matches_for_team(
            team_name=team_name,
            opponent_name=opponent_name,
            season_name=season_name,
            competition_name=competition_name,
            country=country,
            competition_ids=competition_ids,
            use_cache=use_cache,
        ):
            descriptors.setdefault(descriptor.match_id, descriptor)

    return list(descriptors.values())


def _descriptor_to_dict(descriptor: MatchDescriptor) -> Dict[str, object]:
    match = descriptor.match or {}
    competition = match.get("competition", {})
    season = match.get("season", {})
    home = match.get("home_team", {})
    away = match.get("away_team", {})
    return {
        "match_id": descriptor.match_id,
        "competition_id": descriptor.competition_id,
        "season_id": descriptor.season_id,
        "competition_name": competition.get("competition_name"),
        "season_name": season.get("season_name"),
        "match_date": match.get("match_date"),
        "home_team": home.get("home_team_name"),
        "away_team": away.get("away_team_name"),
        "match_status": match.get("match_status"),
        "metadata": match.get("metadata"),
    }


def _normalize_range(
    values: Optional[List[float]],
) -> Optional[Tuple[float, float]]:
    if values is None:
        return None
    items = list(values)
    if len(items) != 2:
        raise ValueError("Range filters must provide exactly two values.")
    return float(items[0]), float(items[1])


def _summarise_player_passes(
    *,
    summary: PlayerEventSummary,
    player_name: str,
    body_part: str,
) -> str:
    matches = len(summary.by_match)
    breakdown = ", ".join(
        f"{match_id}: {count}" for match_id, count in summary.by_match.items()
    )
    return (
        f"{player_name} completed {summary.total} {body_part} pass(es) "
        f"across {matches} match(es). Breakdown: {breakdown or 'none'}."
    )


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
        parts = []
        for field in preview_fields:
            if field in row and row[field] not in (None, ""):
                parts.append(f"{field}={row[field]}")
        if parts:
            lines.append("- " + ", ".join(parts))
    return "\n".join(lines)


def _summarise_metrics(record: Dict[str, Any], mapping: List[Tuple[str, str]]) -> str:
    lines = []
    for key, label in mapping:
        value = record.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, float):
            value = f"{value:.2f}"
        lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def _preview_events(dataset: MatchDataset, limit: int) -> List[Dict[str, object]]:
    preview = []
    for context in dataset.events[: max(limit, 0)]:
        event = context.event
        preview.append(
            {
                "event_id": event.get("id"),
                "type": event.get("type", {}).get("name"),
                "team": event.get("team", {}).get("name"),
                "player": event.get("player", {}).get("name"),
                "minute": event.get("minute"),
                "second": event.get("second"),
                "score_state": context.score_state,
            }
        )
    return preview


__all__ = [
    "register_statsbomb_tools",
    "list_competitions_tool",
    "list_seasons_tool",
    "list_team_matches",
    "count_player_passes_by_body_part_tool",
    "fetch_match_events",
    "fetch_player_season_aggregates",
    "fetch_team_season_aggregates",
    "fetch_player_match_aggregates",
    "player_season_summary_tool",
    "team_season_summary_tool",
    "player_multi_season_summary_tool",
    "compare_player_season_summaries_tool",
    "init_session_with_statsbomb_tools",
]
