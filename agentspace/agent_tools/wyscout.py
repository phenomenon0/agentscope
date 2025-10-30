"""
Agentscope toolkit integration for Wyscout data helpers.
"""

from typing import Any, Dict, Iterable, List, Optional, Sequence

from agentscope.message import TextBlock
from agentscope.tool import Toolkit, ToolResponse

from ..services import data_fetch

WYSCOUT_COMPETITION_IDS: Dict[str, Dict[str, int]] = {
    "England": {
        "Premier League": 364,
    },
    "Spain": {
        "La Liga": 795,
    },
    "Portugal": {
        "Primeira Liga": 707,
    },
    "Italy": {
        "Serie A": 524,
    },
    "Netherlands": {
        "Eredivisie": 635,
    },
}


def _client():
    return data_fetch.get_wyscout_client()


def _flatten_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _flatten_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _flatten_strings(item)


def _string_matches(value: Any, query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    for text in _flatten_strings(value):
        if q in text.lower():
            return True
    return False


def _extract_match_id(match: Dict[str, Any]) -> Optional[int]:
    for key in ("match_id", "matchId", "id"):
        val = match.get(key)
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    return None


def _extract_team_name(match: Dict[str, Any], role: str) -> Optional[str]:
    candidates: Sequence[str] = (
        f"{role}_team",
        f"{role}Team",
        f"{role}team",
        f"{role}TeamName",
        f"{role}teamName",
        role,
    )
    for key in candidates:
        if key in match:
            entry = match[key]
            if isinstance(entry, str):
                return entry
            if isinstance(entry, dict):
                for attr in ("name", "teamName", "shortName", "officialName", "label"):
                    val = entry.get(attr)
                    if isinstance(val, str):
                        return val
    # team1/team2 mapping
    alt_key = "team1" if role == "home" else "team2"
    entry = match.get(alt_key)
    if isinstance(entry, dict):
        for attr in ("name", "teamName", "shortName", "officialName", "label"):
            val = entry.get(attr)
            if isinstance(val, str):
                return val
    # nested teams dict
    teams = match.get("teams")
    if isinstance(teams, dict):
        sub = teams.get(role)
        if isinstance(sub, dict):
            for attr in ("name", "teamName", "shortName", "officialName", "label"):
                val = sub.get(attr)
                if isinstance(val, str):
                    return val
    return None


def _extract_match_date(match: Dict[str, Any]) -> Optional[str]:
    for key in ("date", "matchDate", "gameDate", "startTime", "kickoff"):
        val = match.get(key)
        if isinstance(val, str):
            return val
    return None


def _format_rows(rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> str:
    lines: List[str] = []
    for row in rows[:5]:
        parts = []
        for field in fields:
            parts.append(str(row.get(field, "")))
        lines.append(", ".join(parts))
    return "\n".join(lines)


def list_wyscout_areas(
    *,
    source: str = "common",
    use_cache: bool = True,
) -> ToolResponse:
    """List areas available via the Wyscout API."""

    source_key = source.strip().lower()
    if source_key in ("common", "index", "static"):
        areas = data_fetch.get_wyscout_common_areas()
        resolved_source = "common"
    elif source_key in ("combined", "all"):
        client = _client()
        live = client.list_areas(use_cache=use_cache) or []
        combined: Dict[int, Dict[str, Any]] = {}
        for entry in data_fetch.get_wyscout_common_areas():
            combined[entry.get("id")] = entry
        for entry in live:
            identifier = entry.get("id")
            if isinstance(identifier, int):
                combined[identifier] = entry
        areas = list(combined.values())
        resolved_source = "combined"
    else:
        client = _client()
        areas = client.list_areas(use_cache=use_cache) or []
        resolved_source = "live"

    preview = _format_rows(
        areas,
        fields=["id", "name", "alpha2code"],
    )
    lines = [
        f"Found {len(areas)} Wyscout area(s).",
        f"Source: {resolved_source}",
        "Sample (id, name, alpha2code):",
        preview or "- None",
        "Full list in metadata['areas'].",
    ]
    meta = {"areas": areas, "source": resolved_source}
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=meta)


def list_wyscout_competitions(
    *,
    area_id: Optional[int | str] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """List competitions available via the Wyscout API."""

    client = _client()
    resolved_area = None
    query_area_id: Optional[int] = None

    if isinstance(area_id, str):
        resolved_area = data_fetch.resolve_wyscout_area(area_id)
        if resolved_area is None:
            lines = [
                f"Unable to resolve Wyscout area from '{area_id}'.",
                "Try list_wyscout_areas(source='common') for available IDs.",
            ]
            meta = {
                "competitions": [],
                "filters": {
                    "area_id_input": area_id,
                    "resolved_area": None,
                    "resolved_area_id": None,
                },
            }
            return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=meta)
        query_area_id = resolved_area.get("id")
    else:
        query_area_id = area_id
        if area_id is not None:
            resolved_area = data_fetch.resolve_wyscout_area(area_id)

    competitions = client.list_competitions(area_id=query_area_id, use_cache=use_cache) or []
    preview = _format_rows(
        competitions,
        fields=["competitionId", "name", "category"],
    )
    area_summary = "None"
    if resolved_area:
        area_summary = f"{resolved_area.get('name')} (id={resolved_area.get('id')})"
    elif query_area_id is not None:
        area_summary = f"id={query_area_id}"
    lines = [
        f"Found {len(competitions)} Wyscout competition(s).",
        f"Filter area: {area_summary}",
        "Sample (competitionId, name, category):",
        preview or "- None",
        "Full list in metadata['competitions'].",
    ]
    meta = {
        "competitions": competitions,
        "filters": {
            "area_id_input": area_id,
            "resolved_area_id": query_area_id,
            "resolved_area": resolved_area,
        },
        "known_competition_ids": WYSCOUT_COMPETITION_IDS,
    }
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=meta)


def list_wyscout_seasons(
    competition_id: int,
    *,
    use_cache: bool = True,
) -> ToolResponse:
    """List seasons for a Wyscout competition."""

    client = _client()
    seasons = client.list_seasons(competition_id, use_cache=use_cache) or []
    preview = _format_rows(
        seasons,
        fields=["seasonId", "name", "status"],
    )
    lines = [
        f"Found {len(seasons)} season(s) for Wyscout competition {competition_id}.",
        "Sample (seasonId, name, status):",
        preview or "- None",
        "Full list in metadata['seasons'].",
    ]
    meta = {"competition_id": competition_id, "seasons": seasons}
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=meta)


def list_wyscout_matches(
    competition_id: int,
    season_id: int,
    *,
    team_name: Optional[str] = None,
    opponent_name: Optional[str] = None,
    limit: Optional[int] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """List Wyscout matches for a competition season with optional team filters."""

    client = _client()
    matches = client.list_matches(competition_id, season_id, use_cache=use_cache) or []
    if limit is not None:
        matches = matches[: max(limit, 0)]

    filtered: List[Dict[str, Any]] = []
    for match in matches:
        if team_name and not _string_matches(match, team_name):
            continue
        if opponent_name and not _string_matches(match, opponent_name):
            continue
        filtered.append(match)

    preview_rows: List[Dict[str, Any]] = []
    for match in filtered[:5]:
        match_id = _extract_match_id(match)
        home = _extract_team_name(match, "home")
        away = _extract_team_name(match, "away")
        date = _extract_match_date(match)
        preview_rows.append(
            {
                "match_id": match_id,
                "date": date or "",
                "home": home or "?",
                "away": away or "?",
            }
        )
    preview = _format_rows(preview_rows, fields=["match_id", "date", "home", "away"])

    lines = [
        f"Found {len(filtered)} Wyscout match(es) for competition {competition_id} season {season_id}.",
        "Sample (match_id, date, home, away):",
        preview or "- None",
        "Full matches in metadata['matches'].",
    ]
    meta = {
        "competition_id": competition_id,
        "season_id": season_id,
        "matches": filtered,
        "filters": {
            "team_name": team_name,
            "opponent_name": opponent_name,
            "limit": limit,
        },
    }
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=meta)


def list_wyscout_competition_players(
    competition_id: int,
    *,
    season_id: Optional[int] = None,
    limit: Optional[int] = 1000,
    offset: Optional[int] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """List players registered in a competition (optionally scoped to a season)."""

    client = _client()
    params: Dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    if season_id is not None:
        params["seasonId"] = season_id

    players = client.list_competition_players(
        competition_id,
        params=params or None,
        use_cache=use_cache,
    ) or []

    preview = _format_rows(players, fields=["wyId", "shortName", "role"])
    lines = [
        f"Found {len(players)} player(s) in competition {competition_id}"
        f"{' season ' + str(season_id) if season_id else ''}.",
        "Sample (wyId, shortName, role):",
        preview or "- None",
        "Full list in metadata['players'].",
    ]
    meta = {
        "competition_id": competition_id,
        "season_id": season_id,
        "players": players,
        "params": params,
    }
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=meta)


def get_wyscout_player_advanced_stats(
    player_id: int,
    *,
    competition_id: Optional[int] = None,
    season_id: Optional[int] = None,
    match_id: Optional[int] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """Fetch advanced statistics for a player."""

    client = _client()
    params: Dict[str, Any] = {}
    if competition_id is not None:
        params["competitionId"] = competition_id
    if season_id is not None:
        params["seasonId"] = season_id
    if match_id is not None:
        params["matchId"] = match_id

    stats = client.get_player_advanced_stats(
        player_id,
        params=params or None,
        use_cache=use_cache,
    )
    summary_keys = ", ".join(stats.keys()) if isinstance(stats, dict) else str(type(stats))
    lines = [
        f"Advanced stats retrieved for player {player_id}.",
        f"Keys: {summary_keys}",
    ]
    meta = {
        "player_id": player_id,
        "competition_id": competition_id,
        "season_id": season_id,
        "match_id": match_id,
        "params": params,
        "stats": stats,
    }
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=meta)


def get_wyscout_match_advanced_stats(
    match_id: int,
    *,
    competition_id: Optional[int] = None,
    season_id: Optional[int] = None,
    round_id: Optional[int] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """Fetch match-level advanced statistics."""

    client = _client()
    params: Dict[str, Any] = {}
    if competition_id is not None:
        params["competitionId"] = competition_id
    if season_id is not None:
        params["seasonId"] = season_id
    if round_id is not None:
        params["roundId"] = round_id

    stats = client.get_match_advanced_stats(
        match_id,
        params=params or None,
        use_cache=use_cache,
    )
    summary_keys = ", ".join(stats.keys()) if isinstance(stats, dict) else str(type(stats))
    lines = [
        f"Advanced stats retrieved for match {match_id}.",
        f"Keys: {summary_keys}",
    ]
    meta = {
        "match_id": match_id,
        "competition_id": competition_id,
        "season_id": season_id,
        "round_id": round_id,
        "params": params,
        "stats": stats,
    }
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=meta)


def get_wyscout_match_player_advanced_stats(
    match_id: int,
    *,
    competition_id: Optional[int] = None,
    season_id: Optional[int] = None,
    round_id: Optional[int] = None,
    include_player_details: bool = True,
    use_cache: bool = True,
) -> ToolResponse:
    """Fetch player-level advanced stats for a match."""

    client = _client()
    params: Dict[str, Any] = {}
    if competition_id is not None:
        params["competitionId"] = competition_id
    if season_id is not None:
        params["seasonId"] = season_id
    if round_id is not None:
        params["roundId"] = round_id
    if include_player_details:
        params["detail"] = "player"

    stats = client.get_match_players_advanced_stats(
        match_id,
        params=params or None,
        use_cache=use_cache,
    )
    total = 0
    if isinstance(stats, dict):
        payload = stats.get("players") or stats.get("items")
        if isinstance(payload, list):
            total = len(payload)
    elif isinstance(stats, list):
        total = len(stats)

    lines = [
        f"Player advanced stats retrieved for match {match_id}.",
        f"Records: {total}",
    ]
    meta = {
        "match_id": match_id,
        "competition_id": competition_id,
        "season_id": season_id,
        "round_id": round_id,
        "include_player_details": include_player_details,
        "params": params,
        "stats": stats,
    }
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=meta)


def get_wyscout_events(
    match_id: int,
    *,
    include_player_details: bool = False,
    use_cache: bool = True,
) -> ToolResponse:
    """Fetch detailed event payload for a Wyscout match."""

    client = _client()
    params = {"detail": "player"} if include_player_details else None
    events = client.get_match_events(match_id, params=params, use_cache=use_cache) or {}
    if not events:
        events = client.get_events(match_id, use_cache=use_cache) or {}
    count = 0
    if isinstance(events, dict):
        payload = events.get("events")
        if isinstance(payload, Iterable):
            count = sum(1 for _ in payload)
    elif isinstance(events, list):
        count = len(events)

    lines = [
        f"Wyscout events fetched for match {match_id}.",
        f"Event count (if available): {count}",
        "Payload stored in metadata['events'].",
    ]
    meta = {
        "match_id": match_id,
        "events": events,
        "detail": "player" if include_player_details else None,
    }
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=meta)


def register_wyscout_tools(
    toolkit: Optional[Toolkit] = None,
    *,
    group_name: str = "wyscout",
    activate: bool = True,
) -> Toolkit:
    """
    Register Wyscout data tooling with an Agentscope toolkit.
    """

    toolkit = toolkit or Toolkit()
    try:
        toolkit.create_tool_group(
            group_name,
            description="Wyscout data access helpers.",
            active=activate,
            notes=(
                "Use these tools to pull competitions, seasons, player lists, match schedules, "
                "advanced statistics, and event payloads from the Wyscout API. Provide filters "
                "to minimise payload sizes when possible."
            ),
        )
    except ValueError:
        pass

    toolkit.register_tool_function(
        list_wyscout_areas,
        group_name=group_name,
        func_description="List areas supported by Wyscout.",
    )
    toolkit.register_tool_function(
        list_wyscout_competitions,
        group_name=group_name,
        func_description="List competitions exposed via Wyscout (area_id required).",
    )
    toolkit.register_tool_function(
        list_wyscout_seasons,
        group_name=group_name,
        func_description="List seasons for a Wyscout competition.",
    )
    toolkit.register_tool_function(
        list_wyscout_matches,
        group_name=group_name,
        func_description="List matches for a competition season with optional team/opponent filters.",
    )
    toolkit.register_tool_function(
        list_wyscout_competition_players,
        group_name=group_name,
        func_description="List players registered for a competition (optionally scoped to a season).",
    )
    toolkit.register_tool_function(
        get_wyscout_events,
        group_name=group_name,
        func_description="Fetch event payload for a specific Wyscout match (v4 endpoints).",
    )
    toolkit.register_tool_function(
        get_wyscout_player_advanced_stats,
        group_name=group_name,
        func_description="Fetch advanced statistics for a single player.",
    )
    toolkit.register_tool_function(
        get_wyscout_match_advanced_stats,
        group_name=group_name,
        func_description="Fetch match-level advanced statistics.",
    )
    toolkit.register_tool_function(
        get_wyscout_match_player_advanced_stats,
        group_name=group_name,
        func_description="Fetch player-level advanced statistics for a match.",
    )

    return toolkit
