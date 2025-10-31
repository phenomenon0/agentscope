"""
Event-level analysis tools for detailed player performance investigation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from agentscope.message import TextBlock
from agentscope.tool import Toolkit, ToolResponse

from ..services.statsbomb_tools import (
    find_matches_for_team,
    get_player_season_summary,
    resolve_competition_id,
    season_id_for_label,
)
from ..services.data_fetch import fetch_statsbomb_events


def _error_response(reason: str, metadata: Optional[Dict[str, Any]] = None) -> ToolResponse:
    """Create an error ToolResponse."""
    return ToolResponse(
        content=[TextBlock(type="text", text=reason)],
        metadata=metadata or {"error": reason},
    )


def _extract_metric_value(event: Dict[str, Any], metric_field: str) -> Optional[float]:
    """
    Extract a metric value from an event dictionary.
    Handles nested fields like 'obv_for_after', 'pass.length', etc.
    """
    if "." in metric_field:
        # Nested field like "pass.length"
        parts = metric_field.split(".")
        value = event
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return float(value) if value is not None else None
    else:
        # Top-level field
        value = event.get(metric_field)
        return float(value) if value is not None else None


def get_player_events_ranked_by_metric_tool(
    player_name: str,
    event_type: str,
    metric_field: str,
    season_label: str,
    limit: int = 10,
    team_name: str = "",
    competition_id: int = 0,
    match_limit: int = 5,
    descending: bool = True,
) -> ToolResponse:
    """
    Get top events for a player ranked by a specific metric.

    Args:
        player_name: Player's full name
        event_type: Event type to filter (Pass, Shot, Carry, Dribble, etc.)
        metric_field: Metric to rank by (obv_for_after, obv_for_net, pass_length, etc.)
        season_label: Season (e.g., "2025/2026")
        limit: Number of top events to return (default: 10)
        team_name: Player's team (optional, will auto-detect)
        competition_id: Competition ID (optional, will use player's current comp)
        match_limit: Number of recent matches to analyze (default: 5)
        descending: Rank high-to-low (default: True)

    Returns:
        ToolResponse with ranked event IDs and details

    Example:
        >>> get_player_events_ranked_by_metric_tool(
        ...     player_name="Bukayo Saka",
        ...     event_type="Pass",
        ...     metric_field="obv_for_after",
        ...     season_label="2025/2026",
        ...     limit=10
        ... )
    """
    try:
        # Pass None instead of 0 so get_player_season_summary can auto-resolve
        comp_id_param = competition_id if competition_id and competition_id > 0 else None

        # Get player info
        player_info = get_player_season_summary(
            player_name=player_name,
            season_label=season_label,
            competition_id=comp_id_param,
        )

        if not player_info:
            return _error_response(
                f"Could not find player '{player_name}' in season {season_label}"
            )

        team = team_name if team_name and team_name.strip() else player_info.get("team_name")
        # Use the resolved competition_id from player_info
        comp_id = player_info.get("competition_id")

        if not team:
            return _error_response(
                f"Could not determine team for player {player_name}"
            )

        if not comp_id or comp_id == 0:
            return _error_response(
                f"Could not determine competition for player {player_name}. "
                f"Please provide competition_id parameter."
            )

        # Get season ID
        try:
            season_id = season_id_for_label(comp_id, season_label)
        except Exception as e:
            return _error_response(
                f"Failed to resolve season '{season_label}' for competition {comp_id}: {e}"
            )

        if not season_id:
            return _error_response(
                f"Could not find season ID for {season_label} in competition {comp_id}"
            )

        # Get recent matches
        matches = find_matches_for_team(
            team_name=team,
            competition_ids=[comp_id] if comp_id else None,
            season_name=season_label,
        )

        if not matches:
            return _error_response(
                f"No matches found for {team} in {season_label}"
            )

        # Sort by date descending and take most recent
        matches_sorted = sorted(
            matches,
            key=lambda m: m.get("match_date", ""),
            reverse=True
        )[:match_limit]

        # Collect all events matching criteria
        all_events = []

        for match in matches_sorted:
            match_id = match.get("match_id")
            if not match_id:
                continue

            try:
                events = fetch_statsbomb_events(match_id)
            except Exception as e:
                print(f"Failed to fetch events for match {match_id}: {e}")
                continue

            # Filter events for this player and event type
            for event in events:
                if (event.get("type", {}).get("name") == event_type and
                    event.get("player", {}).get("name") == player_name):

                    # Extract metric value
                    metric_value = _extract_metric_value(event, metric_field)
                    if metric_value is not None:
                        all_events.append({
                            "event_id": event.get("id"),
                            "match_id": match_id,
                            "match_date": match.get("match_date"),
                            "opponent": match.get("home_team" if match.get("away_team") == team else "away_team"),
                            "minute": event.get("minute"),
                            "second": event.get("second"),
                            "period": event.get("period"),
                            "metric_value": metric_value,
                            "event_type": event_type,
                            "location": event.get("location"),
                            "timestamp": event.get("timestamp"),
                        })

        if not all_events:
            return _error_response(
                f"No {event_type} events found for {player_name} with '{metric_field}' data"
            )

        # Sort by metric
        sorted_events = sorted(
            all_events,
            key=lambda e: e["metric_value"],
            reverse=descending
        )[:limit]

        # Build response
        lines = [
            f"🎯 Top {len(sorted_events)} {event_type} Events for {player_name}",
            f"Ranked by: {metric_field} ({'highest' if descending else 'lowest'} first)",
            f"Season: {season_label} | Matches analyzed: {len(matches_sorted)}",
            "",
        ]

        for i, evt in enumerate(sorted_events, 1):
            minute = evt["minute"]
            metric_val = evt["metric_value"]
            opponent = evt.get("opponent", "Unknown")
            match_date = evt.get("match_date", "")

            lines.append(
                f"{i}. **{metric_field}={metric_val:.3f}** | "
                f"min:{minute} | vs {opponent} ({match_date})"
            )
            lines.append(f"   Event ID: `{evt['event_id']}`")

        # Prepare metadata
        metadata = {
            "player_name": player_name,
            "event_type": event_type,
            "metric_field": metric_field,
            "event_count": len(sorted_events),
            "events": sorted_events,
        }

        return ToolResponse(
            content=[TextBlock(type="text", text="\n".join(lines))],
            metadata=metadata,
        )

    except Exception as exc:
        return _error_response(
            f"Failed to rank player events: {exc}",
            metadata={"player_name": player_name, "error": str(exc)}
        )


def get_player_event_sequences_tool(
    player_name: str,
    sequence_type: str,
    season_label: str,
    limit: int = 5,
    team_name: str = "",
    competition_id: int = 0,
    match_limit: int = 5,
) -> ToolResponse:
    """
    Get event sequences involving a player (e.g., buildup to goals, progressive sequences).

    Args:
        player_name: Player's full name
        sequence_type: Type of sequence ("goal_buildup", "progressive_sequence", "shot_buildup")
        season_label: Season (e.g., "2025/2026")
        limit: Number of sequences to return (default: 5)
        team_name: Player's team (optional)
        competition_id: Competition ID (optional)
        match_limit: Number of recent matches to analyze (default: 5)

    Returns:
        ToolResponse with event sequences
    """
    try:
        # Pass None instead of 0 so get_player_season_summary can auto-resolve
        comp_id_param = competition_id if competition_id and competition_id > 0 else None

        # Get player info
        player_info = get_player_season_summary(
            player_name=player_name,
            season_label=season_label,
            competition_id=comp_id_param,
        )

        if not player_info:
            return _error_response(
                f"Could not find player '{player_name}' in season {season_label}"
            )

        team = team_name if team_name and team_name.strip() else player_info.get("team_name")
        comp_id = player_info.get("competition_id")
        season_id = player_info.get("season_id")

        # Get matches
        matches = find_matches_for_team(
            team_name=team,
            competition_ids=[comp_id] if comp_id else None,
            season_name=season_label,
        )

        matches_sorted = sorted(
            matches,
            key=lambda m: m.get("match_date", ""),
            reverse=True
        )[:match_limit]

        sequences = []

        for match in matches_sorted:
            match_id = match.get("match_id")
            if not match_id:
                continue

            try:
                events = fetch_statsbomb_events(match_id)
            except Exception:
                continue

            # Analyze sequences based on type
            if sequence_type == "goal_buildup":
                # Find goals and trace back possessions
                for i, event in enumerate(events):
                    if (event.get("type", {}).get("name") == "Shot" and
                        event.get("shot", {}).get("outcome", {}).get("name") == "Goal"):

                        # Get possession chain leading to goal
                        poss_id = event.get("possession")
                        sequence_events = [
                            e for e in events[:i+1]
                            if e.get("possession") == poss_id and
                               e.get("team", {}).get("name") == team
                        ]

                        # Check if player involved
                        player_involved = any(
                            e.get("player", {}).get("name") == player_name
                            for e in sequence_events
                        )

                        if player_involved:
                            sequences.append({
                                "match_id": match_id,
                                "match_date": match.get("match_date"),
                                "sequence_type": "goal_buildup",
                                "events": sequence_events,
                                "goal_minute": event.get("minute"),
                            })

                    if len(sequences) >= limit:
                        break

            if len(sequences) >= limit:
                break

        if not sequences:
            return _error_response(
                f"No {sequence_type} sequences found for {player_name}"
            )

        # Build response
        lines = [
            f"🔗 {sequence_type.replace('_', ' ').title()} Sequences for {player_name}",
            f"Season: {season_label} | Found: {len(sequences)} sequences",
            "",
        ]

        for i, seq in enumerate(sequences[:limit], 1):
            lines.append(f"{i}. {seq.get('match_date')} - {len(seq['events'])} events")
            lines.append(f"   Goal at minute {seq.get('goal_minute')}")

            # List events in sequence
            for evt in seq["events"][-5:]:  # Last 5 events
                evt_type = evt.get("type", {}).get("name", "Unknown")
                evt_player = evt.get("player", {}).get("name", "Unknown")
                evt_min = evt.get("minute")
                lines.append(f"   • {evt_min}' - {evt_player}: {evt_type}")

        metadata = {
            "player_name": player_name,
            "sequence_type": sequence_type,
            "sequences": sequences,
        }

        return ToolResponse(
            content=[TextBlock(type="text", text="\n".join(lines))],
            metadata=metadata,
        )

    except Exception as exc:
        return _error_response(
            f"Failed to find event sequences: {exc}",
            metadata={"player_name": player_name, "error": str(exc)}
        )


def compare_player_events_tool(
    player1_name: str,
    player2_name: str,
    event_type: str,
    metric_field: str,
    season_label: str,
    limit: int = 10,
    competition_id: int = 0,
    match_limit: int = 5,
) -> ToolResponse:
    """
    Compare event metrics between two players.

    Args:
        player1_name: First player's name
        player2_name: Second player's name
        event_type: Event type to compare
        metric_field: Metric to compare
        season_label: Season
        limit: Top N events per player
        competition_id: Competition ID (optional)
        match_limit: Matches to analyze per player

    Returns:
        ToolResponse with comparison
    """
    try:
        # Get ranked events for both players
        player1_result = get_player_events_ranked_by_metric_tool(
            player_name=player1_name,
            event_type=event_type,
            metric_field=metric_field,
            season_label=season_label,
            limit=limit,
            competition_id=competition_id,
            match_limit=match_limit,
        )

        player2_result = get_player_events_ranked_by_metric_tool(
            player_name=player2_name,
            event_type=event_type,
            metric_field=metric_field,
            season_label=season_label,
            limit=limit,
            competition_id=competition_id,
            match_limit=match_limit,
        )

        # Extract event data
        p1_events = player1_result.metadata.get("events", [])
        p2_events = player2_result.metadata.get("events", [])

        if not p1_events or not p2_events:
            return _error_response(
                "Could not retrieve events for one or both players"
            )

        # Calculate stats
        p1_avg = sum(e["metric_value"] for e in p1_events) / len(p1_events)
        p2_avg = sum(e["metric_value"] for e in p2_events) / len(p2_events)
        p1_max = max(e["metric_value"] for e in p1_events)
        p2_max = max(e["metric_value"] for e in p2_events)

        # Build comparison
        lines = [
            f"⚖️ {player1_name} vs {player2_name}",
            f"Metric: {metric_field} | Event: {event_type} | Season: {season_label}",
            "",
            f"**{player1_name}**",
            f"  Average: {p1_avg:.3f}",
            f"  Peak: {p1_max:.3f}",
            f"  Top events: {len(p1_events)}",
            "",
            f"**{player2_name}**",
            f"  Average: {p2_avg:.3f}",
            f"  Peak: {p2_max:.3f}",
            f"  Top events: {len(p2_events)}",
            "",
            f"**Winner**: {player1_name if p1_avg > p2_avg else player2_name} "
            f"({max(p1_avg, p2_avg):.3f} avg)",
        ]

        metadata = {
            "player1": player1_name,
            "player2": player2_name,
            "player1_avg": p1_avg,
            "player2_avg": p2_avg,
            "player1_events": p1_events,
            "player2_events": p2_events,
        }

        return ToolResponse(
            content=[TextBlock(type="text", text="\n".join(lines))],
            metadata=metadata,
        )

    except Exception as exc:
        return _error_response(
            f"Failed to compare players: {exc}",
            metadata={"error": str(exc)}
        )


def filter_events_by_context_tool(
    player_name: str,
    event_type: str,
    season_label: str,
    context_filters: str,
    limit: int = 20,
    team_name: str = "",
    competition_id: int = 0,
    match_limit: int = 5,
) -> ToolResponse:
    """
    Filter player events by contextual criteria.

    Args:
        player_name: Player's name
        event_type: Event type
        season_label: Season
        context_filters: Dict of filters, e.g.,
            {"under_pressure": True, "zone": "final_third", "minute_range": [75, 90]}
        limit: Max events to return
        team_name: Player's team (optional)
        competition_id: Competition ID (optional)
        match_limit: Matches to analyze

    Returns:
        ToolResponse with filtered events

    Example:
        >>> filter_events_by_context_tool(
        ...     player_name="Bukayo Saka",
        ...     event_type="Pass",
        ...     season_label="2025/2026",
        ...     context_filters='{"under_pressure": true, "zone": "final_third"}'
        ... )
    """
    try:
        # Parse context filters from JSON string
        import json
        if isinstance(context_filters, str):
            try:
                context_filters_dict = json.loads(context_filters)
            except json.JSONDecodeError:
                return _error_response(
                    f"Invalid context_filters JSON: {context_filters}"
                )
        else:
            context_filters_dict = context_filters

        # Pass None instead of 0 so get_player_season_summary can auto-resolve
        comp_id_param = competition_id if competition_id and competition_id > 0 else None

        # Get player info
        player_info = get_player_season_summary(
            player_name=player_name,
            season_label=season_label,
            competition_id=comp_id_param,
        )

        if not player_info:
            return _error_response(
                f"Could not find player '{player_name}' in season {season_label}"
            )

        team = team_name if team_name and team_name.strip() else player_info.get("team_name")
        comp_id = player_info.get("competition_id")
        season_id = player_info.get("season_id")

        # Get matches
        matches = find_matches_for_team(
            team_name=team,
            competition_ids=[comp_id] if comp_id else None,
            season_name=season_label,
        )

        matches_sorted = sorted(
            matches,
            key=lambda m: m.get("match_date", ""),
            reverse=True
        )[:match_limit]

        # Collect filtered events
        filtered_events = []

        for match in matches_sorted:
            match_id = match.get("match_id")
            if not match_id:
                continue

            try:
                events = fetch_statsbomb_events(match_id)
            except Exception:
                continue

            for event in events:
                # Basic filters
                if (event.get("type", {}).get("name") != event_type or
                    event.get("player", {}).get("name") != player_name):
                    continue

                # Apply context filters
                matches_context = True

                # Under pressure
                if context_filters_dict.get("under_pressure"):
                    if not event.get("under_pressure"):
                        matches_context = False

                # Zone filtering (simplified)
                if context_filters_dict.get("zone") and matches_context:
                    location = event.get("location", [0, 0])
                    if len(location) >= 2:
                        x = location[0]
                        zone = context_filters_dict["zone"]
                        if zone == "final_third" and x < 80:
                            matches_context = False
                        elif zone == "middle_third" and (x < 40 or x > 80):
                            matches_context = False
                        elif zone == "defensive_third" and x > 40:
                            matches_context = False

                # Minute range
                if context_filters_dict.get("minute_range") and matches_context:
                    min_range = context_filters_dict["minute_range"]
                    minute = event.get("minute", 0)
                    if minute < min_range[0] or minute > min_range[1]:
                        matches_context = False

                # Pass type (if applicable)
                if context_filters_dict.get("pass_type") and matches_context:
                    pass_type = event.get("pass", {}).get("type", {}).get("name")
                    if pass_type != context_filters_dict["pass_type"]:
                        matches_context = False

                if matches_context:
                    filtered_events.append({
                        "event_id": event.get("id"),
                        "match_id": match_id,
                        "match_date": match.get("match_date"),
                        "minute": event.get("minute"),
                        "location": event.get("location"),
                        "under_pressure": event.get("under_pressure", False),
                        "event": event,
                    })

                if len(filtered_events) >= limit:
                    break

            if len(filtered_events) >= limit:
                break

        if not filtered_events:
            return _error_response(
                f"No events found matching context filters for {player_name}"
            )

        # Build response
        filter_desc = ", ".join(f"{k}={v}" for k, v in context_filters_dict.items())
        lines = [
            f"🔍 Filtered {event_type} Events for {player_name}",
            f"Filters: {filter_desc}",
            f"Season: {season_label} | Found: {len(filtered_events)} events",
            "",
        ]

        for i, evt in enumerate(filtered_events, 1):
            minute = evt["minute"]
            match_date = evt.get("match_date", "")
            pressure = "⚡" if evt.get("under_pressure") else ""

            lines.append(
                f"{i}. min:{minute} {pressure} | {match_date}"
            )
            lines.append(f"   Event ID: `{evt['event_id']}`")

        metadata = {
            "player_name": player_name,
            "event_type": event_type,
            "context_filters": context_filters_dict,
            "event_count": len(filtered_events),
            "events": filtered_events,
        }

        return ToolResponse(
            content=[TextBlock(type="text", text="\n".join(lines))],
            metadata=metadata,
        )

    except Exception as exc:
        return _error_response(
            f"Failed to filter events: {exc}",
            metadata={"player_name": player_name, "error": str(exc)}
        )


def register_event_analysis_tools(
    toolkit: Optional[Toolkit] = None,
    group_name: str = "event-analysis",
    activate: bool = True,
) -> Toolkit:
    """
    Register event analysis tools with the agent toolkit.

    Args:
        toolkit: AgentScope Toolkit instance (creates new if None)
        group_name: Name for this tool group
        activate: Whether to activate the group immediately

    Returns:
        Updated toolkit
    """
    toolkit = toolkit or Toolkit()

    try:
        toolkit.create_tool_group(
            group_name,
            description="Event-level analysis tools for detailed player performance investigation.",
            active=activate,
            notes="Analyze individual events, sequences, and contextual performance.",
        )
    except ValueError:
        # Group already exists
        if activate:
            toolkit.update_tool_groups([group_name], active=True)
    else:
        if activate:
            toolkit.update_tool_groups([group_name], active=True)

    toolkit.register_tool_function(
        get_player_events_ranked_by_metric_tool,
        group_name=group_name,
        func_description="Rank a player's events by a specific metric (OBV, pass length, xT, etc.)",
    )

    toolkit.register_tool_function(
        get_player_event_sequences_tool,
        group_name=group_name,
        func_description="Get event sequences involving a player (goal buildups, progressive sequences)",
    )

    toolkit.register_tool_function(
        compare_player_events_tool,
        group_name=group_name,
        func_description="Compare event metrics between two players",
    )

    toolkit.register_tool_function(
        filter_events_by_context_tool,
        group_name=group_name,
        func_description="Filter player events by context (under pressure, zone, time, etc.)",
    )

    return toolkit
