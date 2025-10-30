"""
Advanced visualization agent tools for player analysis.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentscope.message import Base64Source, ImageBlock, TextBlock
from agentscope.tool import Toolkit, ToolResponse

from ..analytics.pizza_charts import plot_pizza_chart, create_pizza_base64


def _error_response(reason: str, metadata: Optional[Dict[str, Any]] = None) -> ToolResponse:
    """Create an error ToolResponse."""
    return ToolResponse(
        content=[TextBlock(type="text", text=reason)],
        metadata=metadata or {"error": reason},
    )


def plot_pizza_chart_tool(
    player_name: str,
    metrics: Dict[str, float],
    comparison_player: Optional[str] = None,
    comparison_metrics: Optional[Dict[str, float]] = None,
    colors: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
) -> ToolResponse:
    """
    Generate a colorful pizza chart for player performance comparison.

    Args:
        player_name: Name of the main player
        metrics: Dictionary of metric_name -> percentile_value (0-100)
                 Example: {"Shots": 75, "Passes": 82, "Dribbles": 68}
        comparison_player: Name of player to compare against (optional)
        comparison_metrics: Dictionary of metrics for comparison player (optional)
        colors: List of 2 hex colors [player_color, comparison_color] (optional)
        output_dir: Directory to save the chart (optional)

    Returns:
        ToolResponse with the pizza chart image and metadata

    Example:
        >>> plot_pizza_chart_tool(
        ...     player_name="Bukayo Saka",
        ...     metrics={
        ...         "Goals": 85,
        ...         "Assists": 78,
        ...         "Key Passes": 82,
        ...         "Dribbles": 88,
        ...         "Shots": 75,
        ...         "Pass Completion": 80
        ...     }
        ... )
    """
    try:
        # Set output directory
        if output_dir:
            output_path = Path(output_dir) / f"pizza_{player_name.replace(' ', '_')}.png"
        else:
            output_path = Path("plots") / f"pizza_{player_name.replace(' ', '_')}.png"

        # Generate the pizza chart
        result = plot_pizza_chart(
            player_name=player_name,
            values=metrics,
            comparison_player=comparison_player,
            comparison_values=comparison_metrics,
            output_path=output_path,
            colors=colors
        )

        # Read the image and convert to base64
        with open(result.path, 'rb') as f:
            img_data = f.read()
        b64_data = base64.b64encode(img_data).decode('utf-8')

        # Create image block
        image_block = ImageBlock(
            type="image",
            source=Base64Source(
                type="base64",
                media_type="image/png",
                data=b64_data,
            ),
            alt=f"Pizza chart: {player_name}" + (f" vs {comparison_player}" if comparison_player else "")
        )

        # Build text summary
        lines = [
            f"Created pizza chart for {player_name}",
        ]

        if comparison_player:
            lines.append(f"Comparison: {player_name} vs {comparison_player}")

        lines.append(f"Metrics analyzed: {len(metrics)}")
        lines.append(f"Chart saved to: {result.path}")

        # Prepare metadata
        metadata = {
            "viz_type": "pizza_chart",
            "player_name": player_name,
            "comparison_player": comparison_player,
            "metrics": result.metrics,
            "image_path": str(result.path),
            "image_data": b64_data,
            "image_mime_type": "image/png",
            "images": [{
                "data": b64_data,
                "mime_type": "image/png",
                "alt": f"Pizza chart: {player_name}",
                "path": str(result.path)
            }]
        }

        return ToolResponse(
            content=[
                TextBlock(type="text", text="\n".join(lines)),
                image_block,
            ],
            metadata=metadata,
        )

    except Exception as exc:
        return _error_response(
            f"Failed to create pizza chart: {exc}",
            metadata={"player_name": player_name, "error": str(exc)}
        )


def register_advanced_viz_tools(
    toolkit: Toolkit,
    group_name: str = "advanced-viz",
    activate: bool = True
) -> Toolkit:
    """
    Register advanced visualization tools with the agent toolkit.

    Args:
        toolkit: AgentScope Toolkit instance
        group_name: Name for this tool group
        activate: Whether to activate the group immediately

    Returns:
        Updated toolkit
    """
    toolkit.add_function(
        plot_pizza_chart_tool,
        group_name=group_name,
        activate=activate
    )

    return toolkit
