"""
Agent toolkit for StatsBomb visualizations via mplsoccer.
"""

import base64
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

from agentscope.message import Base64Source, ImageBlock, TextBlock
from agentscope.tool import Toolkit, ToolResponse

from ..analytics.mplsoccer_viz import plot_match_shot_map, plot_event_heatmap, plot_pass_network
from ..services.statsbomb_tools import MatchDescriptor, fetch_match_dataset


def _error_response(reason: str, metadata: Optional[dict[str, Any]] = None) -> ToolResponse:
    return ToolResponse(
        content=[TextBlock(type="text", text=reason)],
        metadata=metadata or {"error": reason},
    )


def _image_payload(
    path: Path,
    *,
    mime_type: str = "image/png",
    alt: Optional[str] = None,
) -> Tuple[ImageBlock, dict[str, Any]]:
    data_encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    block = ImageBlock(
        type="image",
        source=Base64Source(
            type="base64",
            media_type=mime_type,
            data=data_encoded,
        ),
    )
    metadata = {
        "path": str(path),
        "mime_type": mime_type,
        "data": data_encoded,
    }
    if alt:
        metadata["alt"] = alt
    return block, metadata


def plot_match_shot_map_tool(
    match_id: int,
    *,
    competition_id: Optional[int] = None,
    season_id: Optional[int] = None,
    team_name: Optional[str] = None,
    include_opponent: bool = True,
    output_dir: Optional[str] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """
    Generate a shot map for the specified match.
    """

    descriptor = MatchDescriptor(
        match_id=match_id,
        competition_id=competition_id,
        season_id=season_id,
    )
    try:
        dataset = fetch_match_dataset(
            descriptor,
            use_cache=use_cache,
        )
    except Exception as exc:  # pragma: no cover - network failures
        return _error_response(f"Failed to fetch match data: {exc}")

    try:
        result = plot_match_shot_map(
            dataset,
            team_name=team_name,
            include_opponent=include_opponent,
            output_dir=output_dir,
        )
    except Exception as exc:
        return _error_response(f"Failed to render shot map: {exc}")

    lines = [
        f"Created shot map for match {match_id}{f' ({team_name})' if team_name else ''}.",
        f"Shots: {result.total_shots} with {result.total_goals} goal(s).",
    ]
    if include_opponent:
        lines.append(f"Opponent shots: {result.opponent_shots} (Goals: {result.opponent_goals}).")
    lines.append("Attached figure shows shot locations sized by xG; stars mark goals.")

    team_label = result.team_name or "Unknown team"
    opponent_label = result.opponent_name or "opponent"
    alt_text = f"Shot map for {team_label} vs {opponent_label}" if result.opponent_name else f"Shot map for {team_label}"
    image_block, image_meta = _image_payload(
        Path(result.path),
        alt=alt_text,
    )

    metadata = {
        "image_path": str(result.path),
        "image_mime_type": "image/png",
        "image_data": image_meta.get("data"),
        "team_name": result.team_name,
        "opponent_name": result.opponent_name,
        "match_id": result.match_id,
        "competition_id": result.competition_id,
        "season_id": result.season_id,
        "total_shots": result.total_shots,
        "total_goals": result.total_goals,
        "opponent_shots": result.opponent_shots,
        "opponent_goals": result.opponent_goals,
        "viz_type": "shot_map",
        "images": [image_meta],
    }

    return ToolResponse(
        content=[
            TextBlock(type="text", text="\n".join(lines)),
            image_block,
        ],
        metadata=metadata,
    )


def plot_event_heatmap_tool(
    match_id: int,
    *,
    team_name: str,
    event_types: Optional[Sequence[str]] = None,
    bins_x: int = 24,
    bins_y: int = 16,
    output_dir: Optional[str] = None,
    competition_id: Optional[int] = None,
    season_id: Optional[int] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """
    Generate an on-ball action heatmap for a team in a given match.
    """

    descriptor = MatchDescriptor(
        match_id=match_id,
        competition_id=competition_id,
        season_id=season_id,
    )
    try:
        dataset = fetch_match_dataset(
            descriptor,
            use_cache=use_cache,
        )
    except Exception as exc:  # pragma: no cover
        return _error_response(f"Failed to fetch match data: {exc}")

    events = event_types or ("Pass", "Carry", "Dribble")
    try:
        result = plot_event_heatmap(
            dataset,
            team_name=team_name,
            event_types=events,
            bins=(bins_x, bins_y),
            output_dir=output_dir,
        )
    except Exception as exc:
        return _error_response(f"Failed to render heatmap: {exc}")

    lines = [
        f"Created heatmap for {team_name} in match {match_id}.",
        f"Events considered: {', '.join(events)} ({result.sample_size} records).",
        "Attached heatmap highlights the highest-density zones for those actions.",
    ]
    team_label = result.team_name or team_name
    image_block, image_meta = _image_payload(
        Path(result.path),
        alt=f"Event heatmap for {team_label}",
    )

    metadata = {
        "image_path": str(result.path),
        "image_mime_type": "image/png",
        "image_data": image_meta.get("data"),
        "team_name": result.team_name,
        "match_id": result.match_id,
        "competition_id": result.competition_id,
        "season_id": result.season_id,
        "event_types": list(events),
        "sample_size": result.sample_size,
        "viz_type": "event_heatmap",
        "images": [image_meta],
    }

    return ToolResponse(
        content=[
            TextBlock(type="text", text="\n".join(lines)),
            image_block,
        ],
        metadata=metadata,
    )


def plot_pass_network_tool(
    match_id: int,
    *,
    team_name: str,
    competition_id: Optional[int] = None,
    season_id: Optional[int] = None,
    min_pass_count: int = 3,
    output_dir: Optional[str] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """
    Generate a pass network visual for a team's completed passes.
    """

    descriptor = MatchDescriptor(
        match_id=match_id,
        competition_id=competition_id,
        season_id=season_id,
    )
    try:
        dataset = fetch_match_dataset(
            descriptor,
            use_cache=use_cache,
        )
    except Exception as exc:  # pragma: no cover
        return _error_response(f"Failed to fetch match data: {exc}")

    try:
        result = plot_pass_network(
            dataset,
            team_name=team_name,
            min_pass_count=min_pass_count,
            output_dir=output_dir,
        )
    except Exception as exc:
        return _error_response(f"Failed to render pass network: {exc}")

    lines = [
        f"Created pass network for {team_name} in match {match_id}.",
        f"Connections shown: {result.edge_count}, player nodes: {result.node_count}.",
        f"Total completed passes represented: {result.total_passes}.",
        "Attached graphic plots average player positions with line widths scaled by pass volume.",
    ]
    team_label = result.team_name or team_name
    image_block, image_meta = _image_payload(
        Path(result.path),
        alt=f"Pass network for {team_label}",
    )

    metadata = {
        "image_path": str(result.path),
        "image_mime_type": "image/png",
        "image_data": image_meta.get("data"),
        "team_name": result.team_name,
        "match_id": result.match_id,
        "competition_id": result.competition_id,
        "season_id": result.season_id,
        "edge_count": result.edge_count,
        "node_count": result.node_count,
        "total_passes": result.total_passes,
        "viz_type": "pass_network",
        "images": [image_meta],
    }

    return ToolResponse(
        content=[
            TextBlock(type="text", text="\n".join(lines)),
            image_block,
        ],
        metadata=metadata,
    )


def register_statsbomb_viz_tools(
    toolkit: Optional[Toolkit] = None,
    *,
    group_name: str = "statsbomb-viz",
    activate: bool = True,
) -> Toolkit:
    """
    Register visualization-oriented tools built on StatsBomb data.
    """

    toolkit = toolkit or Toolkit()
    try:
        toolkit.create_tool_group(
            group_name,
            description="Visualization tools rendering StatsBomb data via mplsoccer.",
            active=activate,
            notes="Generates PNG pitch plots; ensure mplsoccer/matplotlib dependencies are installed.",
        )
    except ValueError:
        # Group already exists; continue registering functions.
        if activate:
            toolkit.update_tool_groups([group_name], active=True)
    else:
        if activate:
            toolkit.update_tool_groups([group_name], active=True)
    toolkit.register_tool_function(
        plot_match_shot_map_tool,
        group_name=group_name,
        func_description="Render a StatsBomb shot map with mplsoccer.",
    )
    toolkit.register_tool_function(
        plot_event_heatmap_tool,
        group_name=group_name,
        func_description="Render a StatsBomb on-ball heatmap with mplsoccer.",
    )
    toolkit.register_tool_function(
        plot_pass_network_tool,
        group_name=group_name,
        func_description="Render a StatsBomb pass network using mplsoccer.",
    )
    return toolkit


__all__ = [
    "register_statsbomb_viz_tools",
    "plot_match_shot_map_tool",
    "plot_event_heatmap_tool",
    "plot_pass_network_tool",
]
