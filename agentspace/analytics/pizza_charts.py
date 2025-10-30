"""
Pizza chart visualizations for player comparison.
Based on mplsoccer examples.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager as fm
from mplsoccer import PyPizza

from .viz_config import PIZZA_COLORS, get_team_color


@dataclass
class PizzaChartResult:
    """Result from pizza chart generation."""
    path: Path
    player_name: str
    comparison_player: Optional[str]
    metrics: List[str]
    values: List[float]
    comparison_values: Optional[List[float]]


def plot_pizza_chart(
    player_name: str,
    values: Dict[str, float],
    comparison_player: Optional[str] = None,
    comparison_values: Optional[Dict[str, float]] = None,
    output_path: Optional[Path] = None,
    colors: Optional[List[str]] = None,
    title: Optional[str] = None,
) -> PizzaChartResult:
    """
    Create a colorful pizza chart for player comparison.

    Args:
        player_name: Name of the main player
        values: Dict of metric_name -> value (0-100 percentiles)
        comparison_player: Name of comparison player (optional)
        comparison_values: Dict of metric_name -> value for comparison (optional)
        output_path: Where to save the chart
        colors: List of 2 colors [player_color, comparison_color]
        title: Custom title (default: auto-generated)

    Returns:
        PizzaChartResult with path and metadata
    """
    # Prepare data
    metrics = list(values.keys())
    player_vals = list(values.values())

    comp_vals = None
    if comparison_values:
        comp_vals = [comparison_values.get(m, 0) for m in metrics]

    # Set colors
    if not colors:
        colors = PIZZA_COLORS['blue_gold']

    # Create title
    if not title:
        if comparison_player:
            title = f"{player_name} vs {comparison_player}"
        else:
            title = f"{player_name} - Season Performance"

    # Create the pizza chart
    baker = PyPizza(
        params=metrics,
        background_color="#222222",
        straight_line_color="#000000",
        straight_line_lw=1,
        last_circle_lw=0,
        other_circle_lw=0,
        inner_circle_size=20
    )

    # Plot
    fig, ax = baker.make_pizza(
        player_vals,
        compare_values=comp_vals,
        figsize=(10, 10),
        color_blank_space=["#1a1a1a"] * len(metrics),
        slice_colors=[colors[0]] * len(metrics),
        value_colors=[colors[0]] * len(metrics),
        value_bck_colors=["#222222"] * len(metrics),
        blank_alpha=0.4,
        kwargs_slices=dict(
            edgecolor="#000000",
            zorder=2,
            linewidth=1
        ),
        kwargs_compare=dict(
            facecolor=colors[1] if len(colors) > 1 else "#ff9300",
            edgecolor="#000000",
            zorder=2,
            linewidth=1,
        ) if comp_vals else None,
        kwargs_params=dict(
            color="#F2F2F2",
            fontsize=12,
            va="center"
        ),
        kwargs_values=dict(
            color="#F2F2F2",
            fontsize=11,
            zorder=3,
            bbox=dict(
                edgecolor="#000000",
                facecolor="cornflowerblue",
                boxstyle="round,pad=0.2",
                lw=1
            )
        )
    )

    # Add title
    fig.text(
        0.515, 0.97,
        title,
        size=20,
        ha="center",
        color="#F2F2F2",
        weight="bold"
    )

    # Add subtitle with player names
    if comparison_player:
        fig.text(
            0.515, 0.94,
            f"{player_name} (blue) vs {comparison_player} (orange)",
            size=14,
            ha="center",
            color="#F2F2F2"
        )
    else:
        fig.text(
            0.515, 0.94,
            "Percentile rankings vs league average",
            size=12,
            ha="center",
            color="#999999"
        )

    # Save
    if not output_path:
        output_path = Path("plots") / f"pizza_{player_name.replace(' ', '_')}.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='#222222')
    plt.close(fig)

    return PizzaChartResult(
        path=output_path,
        player_name=player_name,
        comparison_player=comparison_player,
        metrics=metrics,
        values=player_vals,
        comparison_values=comp_vals
    )


def create_pizza_base64(
    player_name: str,
    values: Dict[str, float],
    comparison_player: Optional[str] = None,
    comparison_values: Optional[Dict[str, float]] = None,
    colors: Optional[List[str]] = None,
) -> Tuple[str, Dict]:
    """
    Create pizza chart and return as base64 string.

    Returns:
        Tuple of (base64_string, metadata_dict)
    """
    # Create temporary path
    temp_path = Path("plots") / f"temp_pizza_{player_name.replace(' ', '_')}.png"

    # Generate chart
    result = plot_pizza_chart(
        player_name=player_name,
        values=values,
        comparison_player=comparison_player,
        comparison_values=comparison_values,
        output_path=temp_path,
        colors=colors
    )

    # Read and encode
    with open(result.path, 'rb') as f:
        img_data = f.read()

    b64_data = base64.b64encode(img_data).decode('utf-8')

    metadata = {
        'viz_type': 'pizza_chart',
        'player_name': player_name,
        'comparison_player': comparison_player,
        'metrics': result.metrics,
        'image_path': str(result.path),
    }

    return b64_data, metadata


def plot_simple_radar(
    player_name: str,
    values: Dict[str, float],
    output_path: Optional[Path] = None,
    color: Optional[str] = None,
    title: Optional[str] = None,
) -> Path:
    """
    Create a simple radar/spider chart for a player.

    Args:
        player_name: Player name
        values: Dict of metric -> value (0-100)
        output_path: Where to save
        color: Fill color
        title: Custom title

    Returns:
        Path to saved chart
    """
    metrics = list(values.keys())
    vals = list(values.values())

    # Number of variables
    num_vars = len(metrics)

    # Compute angle for each axis
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    vals += vals[:1]  # Complete the circle
    angles += angles[:1]

    # Set color
    if not color:
        color = '#1a78cf'

    # Create plot
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    # Draw one axis per variable
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, size=12)

    # Set y limits
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], size=10, color='gray')

    # Plot data
    ax.plot(angles, vals, 'o-', linewidth=2, color=color, label=player_name)
    ax.fill(angles, vals, alpha=0.25, color=color)

    # Add title
    if not title:
        title = f"{player_name} - Performance Radar"
    plt.title(title, size=18, y=1.08, weight='bold')

    # Add grid
    ax.grid(True, linestyle='--', alpha=0.7)

    # Save
    if not output_path:
        output_path = Path("plots") / f"radar_{player_name.replace(' ', '_')}.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

    return output_path
