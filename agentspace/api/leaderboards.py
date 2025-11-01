"""
Utility helpers for season leaderboard endpoints.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Optional, Tuple

from agentspace.agent_tools.rankings import (
    player_percentile_snapshot_tool,
    rank_players_by_metric_tool,
)


def _first_text_block(content: Optional[Any]) -> str:
    """Extract plain text from the first TextBlock-style entry."""
    if not content:
        return ""
    for block in content:
        if isinstance(block, Mapping):
            text = block.get("text")
        else:
            text = getattr(block, "text", None)
        if text:
            return str(text)
    return ""


def get_player_leaderboard(
    *,
    metric_name: str,
    season_label: str,
    competitions: Optional[str],
    limit: int,
    sort_order: str,
    min_minutes: Optional[float],
    position_bucket: Optional[str],
) -> Tuple[str, Dict[str, Any]]:
    response = rank_players_by_metric_tool(
        metric_name=metric_name,
        season_label=season_label,
        competitions=competitions,
        limit=limit,
        sort_order=sort_order,
        min_minutes=min_minutes,
        position_bucket=position_bucket,
    )
    metadata = response.metadata or {}
    text = _first_text_block(response.content)
    return text, metadata


def get_player_percentile_snapshot(
    *,
    season_label: str,
    player_id: Optional[int],
    player_name: Optional[str],
    competition_id: Optional[int],
    competitions: Optional[str],
    limit: int,
    position_bucket: Optional[str],
) -> Tuple[str, Dict[str, Any]]:
    response = player_percentile_snapshot_tool(
        player_name=player_name,
        player_id=player_id,
        season_label=season_label,
        competition_id=competition_id,
        competitions=competitions,
        limit=limit,
        position_bucket=position_bucket,
    )
    metadata = response.metadata or {}
    text = _first_text_block(response.content)
    return text, metadata
