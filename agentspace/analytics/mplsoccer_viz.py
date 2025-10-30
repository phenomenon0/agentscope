"""
Visualization helpers using the mplsoccer toolkit.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from .statsbomb_processors import events_to_dataframe
from ..services.statsbomb_tools import MatchDataset, MatchDescriptor

StatsFrame = Union[pd.DataFrame, MatchDataset]


@dataclass(frozen=True)
class ShotMapResult:
    """Metadata describing a rendered shot map."""

    path: Path
    team_name: Optional[str]
    opponent_name: Optional[str]
    match_id: Optional[int]
    competition_id: Optional[int]
    season_id: Optional[int]
    total_shots: int
    total_goals: int
    opponent_shots: int
    opponent_goals: int


@dataclass(frozen=True)
class HeatmapResult:
    """Metadata describing a rendered action heatmap."""

    path: Path
    team_name: Optional[str]
    event_types: Tuple[str, ...]
    match_id: Optional[int]
    competition_id: Optional[int]
    season_id: Optional[int]
    sample_size: int


@dataclass(frozen=True)
class PassNetworkResult:
    """Metadata describing a rendered pass network."""

    path: Path
    team_name: Optional[str]
    match_id: Optional[int]
    competition_id: Optional[int]
    season_id: Optional[int]
    edge_count: int
    node_count: int
    total_passes: int


def _load_mplsoccer():
    """
    Import mplsoccer and matplotlib lazily to avoid mandatory dependency at import time.
    """

    try:
        from mplsoccer import Pitch  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError as exc:  # pragma: no cover - handled by caller
        raise RuntimeError(
            "mplsoccer is required for visualization tools. "
            "Install it with `pip install mplsoccer`."
        ) from exc
    return Pitch, plt


def _ensure_dataframe(data: StatsFrame) -> Tuple[pd.DataFrame, Optional[MatchDataset]]:
    if isinstance(data, pd.DataFrame):
        return data.copy(), None
    return events_to_dataframe(data), data


def _ensure_output_dir(output_dir: Optional[Union[str, Path]]) -> Path:
    if output_dir is None:
        base = os.getenv("AGENTSPACE_VIZ_DIR", "plots")
        output_dir = Path(base)
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _normalize_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Scale positional columns to StatsBomb's 120x80 pitch if required.
    """

    coords = df[
        [
            col
            for col in (
                "location_x",
                "pass_end_x",
                "carry_end_x",
                "shot_end_x",
            )
            if col in df
        ]
    ].to_numpy(dtype=float, copy=True)
    all_x = coords[~np.isnan(coords)]
    scale_x = _estimate_scale(all_x, target=120.0)

    coords_y = df[
        [
            col
            for col in (
                "location_y",
                "pass_end_y",
                "carry_end_y",
                "shot_end_y",
            )
            if col in df
        ]
    ].to_numpy(dtype=float, copy=True)
    all_y = coords_y[~np.isnan(coords_y)]
    scale_y = _estimate_scale(all_y, target=80.0)

    if scale_x != 1.0:
        for column in ("location_x", "pass_end_x", "carry_end_x", "shot_end_x"):
            if column in df:
                df[column] = df[column].astype(float) * scale_x

    if scale_y != 1.0:
        for column in ("location_y", "pass_end_y", "carry_end_y", "shot_end_y"):
            if column in df:
                df[column] = df[column].astype(float) * scale_y
    return df


def _estimate_scale(values: np.ndarray, target: float) -> float:
    if values.size == 0:
        return 1.0
    max_val = np.nanmax(values)
    if max_val == 0 or np.isnan(max_val):
        return 1.0

    if max_val <= 1.5:
        return target  # normalised 0-1 input
    if 10.0 < max_val < target * 0.92:
        return target / max_val  # likely 100 or 105 sized pitch
    if max_val > target * 1.1:
        return target / max_val  # larger scale than expected
    return 1.0


def plot_match_shot_map(
    data: StatsFrame,
    *,
    team_name: Optional[str] = None,
    include_opponent: bool = True,
    output_dir: Optional[Union[str, Path]] = None,
    filename: Optional[str] = None,
) -> ShotMapResult:
    """
    Render a shot map for a match using mplsoccer.
    """

    events_df, dataset = _ensure_dataframe(data)
    if events_df.empty:
        raise ValueError("No events available to plot.")

    events_df = _normalize_coordinates(events_df)
    shots = events_df[events_df["event_type"] == "Shot"].copy()
    shots = shots.dropna(subset=["location_x", "location_y"])
    if shots.empty:
        raise ValueError("No shot events available to plot.")

    descriptor = dataset.descriptor if dataset else None
    primary_mask = (
        shots["team"].str.lower().eq(team_name.lower())
        if team_name
        else pd.Series([True] * len(shots), index=shots.index)
    )
    primary_shots = shots[primary_mask]
    opponent_shots = shots[~primary_mask] if include_opponent else pd.DataFrame(columns=shots.columns)

    if include_opponent and not opponent_shots.empty:
        opponent_shots = opponent_shots.copy()
        opponent_shots["location_x"] = 120.0 - opponent_shots["location_x"].astype(float)
        opponent_shots["location_y"] = 80.0 - opponent_shots["location_y"].astype(float)

    if team_name and primary_shots.empty:
        raise ValueError(f"No shots found for team '{team_name}'.")

    palette = {
        "primary": {"shot": "#1f77b4", "goal": "#2ca02c"},
        "opponent": {"shot": "#d62728", "goal": "#ff7f0e"},
    }

    Pitch, plt = _load_mplsoccer()
    pitch = Pitch(
        pitch_type="statsbomb",
        line_zorder=2,
        pitch_color="#f9f9f9",
        line_color="#22313f",
    )
    fig, ax = pitch.draw(figsize=(10, 7), constrained_layout=True)
    fig.set_facecolor("#f9f9f9")

    def _scatter_shots(frame: pd.DataFrame, color_key: str, label_prefix: str) -> Tuple[int, int]:
        if frame.empty:
            return 0, 0
        frame = frame.copy()
        frame["is_goal"] = frame["shot_outcome"].str.lower() == "goal"
        frame["marker_size"] = (frame["shot_xg"].fillna(0.05) * 900).clip(lower=80)

        non_goal = frame[~frame["is_goal"]]
        if not non_goal.empty:
            pitch.scatter(
                non_goal["location_x"],
                non_goal["location_y"],
                s=non_goal["marker_size"],
                edgecolors="black",
                linewidths=0.5,
                alpha=0.75,
                c=palette[color_key]["shot"],
                ax=ax,
                label=f"{label_prefix} shots",
                zorder=3,
            )
        goals = frame[frame["is_goal"]]
        if not goals.empty:
            pitch.scatter(
                goals["location_x"],
                goals["location_y"],
                s=goals["marker_size"] * 1.15,
                marker="*",
                edgecolors="black",
                linewidths=0.8,
                alpha=0.9,
                c=palette[color_key]["goal"],
                ax=ax,
                label=f"{label_prefix} goals",
                zorder=4,
            )
        return len(frame), int(goals["is_goal"].sum())

    team_label = team_name or "All teams"
    total_shots, total_goals = _scatter_shots(primary_shots, "primary", team_label)
    opp_shots_count = 0
    opp_goals_count = 0
    if include_opponent and not opponent_shots.empty:
        opp_name = opponent_shots["team"].mode().iloc[0] if not opponent_shots.empty else "Opponent"
        opp_shots_count, opp_goals_count = _scatter_shots(opponent_shots, "opponent", f"{opp_name} (flipped)")

    title_segments: list[str] = []
    if descriptor:
        teams = _matchup_label(descriptor.match)
        if teams:
            title_segments.append(teams)
    title_segments.append("Shot map")
    if team_name:
        title_segments.append(team_name)
    ax.set_title(" – ".join(title_segments), fontsize=14, weight="bold")
    ax.legend(loc="upper right", fontsize=10, frameon=False)

    output_dir_path = _ensure_output_dir(output_dir)
    if not filename:
        slug_team = _slug(team_name or "all")
        match_id = descriptor.match_id if descriptor else "unknown"
        filename = f"shot-map_match-{match_id}_{slug_team}.png"
    output_path = output_dir_path / filename
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    opponent_name = None
    if descriptor and descriptor.match:
        opponent_name = _opponent_from_match(descriptor.match, team_name)

    return ShotMapResult(
        path=output_path,
        team_name=team_name,
        opponent_name=opponent_name,
        match_id=descriptor.match_id if descriptor else None,
        competition_id=descriptor.competition_id if descriptor else None,
        season_id=descriptor.season_id if descriptor else None,
        total_shots=total_shots,
        total_goals=total_goals,
        opponent_shots=opp_shots_count,
        opponent_goals=opp_goals_count,
    )


def plot_event_heatmap(
    data: StatsFrame,
    *,
    team_name: Optional[str],
    event_types: Sequence[str] = ("Pass", "Carry", "Dribble"),
    bins: Tuple[int, int] = (24, 16),
    output_dir: Optional[Union[str, Path]] = None,
    filename: Optional[str] = None,
) -> HeatmapResult:
    """
    Render an action density heatmap for the specified team and event types.
    """

    if not event_types:
        raise ValueError("event_types must include at least one event type.")

    events_df, dataset = _ensure_dataframe(data)
    if events_df.empty:
        raise ValueError("No events available to plot.")

    events_df = _normalize_coordinates(events_df)
    filtered = events_df[
        (events_df["team"].str.lower() == team_name.lower())
        if team_name
        else pd.Series([True] * len(events_df), index=events_df.index)
    ]
    filtered = filtered[filtered["event_type"].isin(event_types)]
    filtered = filtered.dropna(subset=["location_x", "location_y"])
    if filtered.empty:
        raise ValueError("No matching events found for heatmap.")

    Pitch, plt = _load_mplsoccer()
    pitch = Pitch(
        pitch_type="statsbomb",
        line_zorder=2,
        pitch_color="#0b132b",
        line_color="#d7d7d7",
    )
    fig, ax = pitch.draw(figsize=(9, 6))
    fig.set_facecolor("#0b132b")

    bin_statistic = pitch.bin_statistic(
        filtered["location_x"],
        filtered["location_y"],
        bins=bins,
        statistic="count",
    )
    pitch.heatmap(
        bin_statistic,
        ax=ax,
        cmap="magma",
        edgecolor="white",
        lw=0.1,
    )
    ax.set_title(
        _heatmap_title(team_name, dataset.descriptor if dataset else None, event_types),
        fontsize=14,
        color="#ffffff",
        weight="bold",
    )

    output_dir_path = _ensure_output_dir(output_dir)
    if not filename:
        slug_team = _slug(team_name or "all")
        match_id = dataset.descriptor.match_id if dataset else "unknown"
        filename = f"heatmap_match-{match_id}_{slug_team}_{_slug('_'.join(event_types))}.png"
    output_path = output_dir_path / filename
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    descriptor = dataset.descriptor if dataset else None
    return HeatmapResult(
        path=output_path,
        team_name=team_name,
        event_types=tuple(event_types),
        match_id=descriptor.match_id if descriptor else None,
        competition_id=descriptor.competition_id if descriptor else None,
        season_id=descriptor.season_id if descriptor else None,
        sample_size=len(filtered),
    )


def plot_pass_network(
    data: StatsFrame,
    *,
    team_name: str,
    min_pass_count: int = 3,
    output_dir: Optional[Union[str, Path]] = None,
    filename: Optional[str] = None,
) -> PassNetworkResult:
    """
    Render a pass network for a team, showing the most common passing links.
    """

    if min_pass_count <= 0:
        raise ValueError("min_pass_count must be greater than zero.")

    events_df, dataset = _ensure_dataframe(data)
    if events_df.empty:
        raise ValueError("No events available to plot.")

    events_df = _normalize_coordinates(events_df)
    passes = events_df[
        (events_df["team"].str.lower() == team_name.lower())
        & (events_df["event_type"] == "Pass")
    ].copy()
    passes["pass_outcome"] = passes["pass_outcome"].fillna("Complete")
    passes = passes[
        (passes["pass_outcome"] == "Complete")
        & passes["pass_recipient_id"].notna()
        & passes["location_x"].notna()
        & passes["location_y"].notna()
        & passes["pass_end_x"].notna()
        & passes["pass_end_y"].notna()
    ]
    if passes.empty:
        raise ValueError(f"No completed passes found for team '{team_name}'.")

    pass_counts = passes.groupby(
        ["player_id", "pass_recipient_id"], as_index=False
    ).size()
    pass_counts.rename(columns={"size": "pass_count"}, inplace=True)
    pass_counts = pass_counts[pass_counts["pass_count"] >= min_pass_count]

    if pass_counts.empty:
        raise ValueError(
            f"No pass links meet the minimum threshold of {min_pass_count} for '{team_name}'."
        )

    player_positions = passes.groupby("player_id").agg(
        start_x=("location_x", "mean"),
        start_y=("location_y", "mean"),
        player_name=("player_name", "first"),
    )
    passes_made = passes.groupby("player_id").size().rename("passes_made")
    player_positions = player_positions.join(passes_made)

    recipient_positions = passes.groupby("pass_recipient_id").agg(
        recv_x=("pass_end_x", "mean"),
        recv_y=("pass_end_y", "mean"),
        recipient_name=("pass_recipient_name", "first"),
    )
    passes_received = passes.groupby("pass_recipient_id").size().rename("passes_received")
    recipient_positions = recipient_positions.join(passes_received)
    recipient_positions.index.name = "player_id"

    combined = player_positions.join(recipient_positions, how="outer")
    combined["player_name"] = combined["player_name"].fillna(combined["recipient_name"])
    combined["passes_made"] = combined["passes_made"].fillna(0)
    combined["passes_received"] = combined["passes_received"].fillna(0)
    combined["passes_total"] = combined["passes_made"] + combined["passes_received"]

    combined["x"] = combined[["start_x", "recv_x"]].mean(axis=1)
    combined["y"] = combined[["start_y", "recv_y"]].mean(axis=1)
    combined = combined.dropna(subset=["x", "y"])
    if combined.empty:
        raise ValueError(f"Unable to determine pass locations for team '{team_name}'.")

    combined["label"] = combined["player_name"].fillna("Unknown").apply(_short_name)
    nodes = combined.loc[
        combined.index.isin(pass_counts["player_id"]) | combined.index.isin(pass_counts["pass_recipient_id"])
    ]

    Pitch, plt = _load_mplsoccer()
    pitch = Pitch(
        pitch_type="statsbomb",
        line_zorder=2,
        pitch_color="#13293d",
        line_color="#f3f5f4",
    )
    fig, ax = pitch.draw(figsize=(10, 7), constrained_layout=True)
    fig.set_facecolor("#13293d")

    node_sizes = nodes["passes_total"]
    if node_sizes.max() > 0:
        node_sizes = (node_sizes / node_sizes.max()) * 1600
    node_sizes = node_sizes.clip(lower=250)

    if nodes["passes_total"].max() > 0:
        node_colors = (nodes["passes_total"] - nodes["passes_total"].min()) / (
            nodes["passes_total"].max() - nodes["passes_total"].min() or 1
        )
    else:
        node_colors = np.zeros(len(nodes))
    node_palette = plt.cm.viridis(node_colors)

    pitch.scatter(
        nodes["x"],
        nodes["y"],
        s=node_sizes,
        color=node_palette,
        edgecolors="white",
        linewidths=1.2,
        alpha=0.9,
        ax=ax,
        zorder=4,
    )

    for _, row in nodes.iterrows():
        ax.text(
            row["x"],
            row["y"],
            row["label"],
            ha="center",
            va="center",
            fontsize=9,
            weight="bold",
            color="#0d1b2a",
            zorder=5,
        )

    for edge in pass_counts.itertuples():
        if edge.player_id not in combined.index or edge.pass_recipient_id not in combined.index:
            continue
        origin = combined.loc[edge.player_id]
        target = combined.loc[edge.pass_recipient_id]
        width = max(1.2, float(edge.pass_count))
        alpha = min(0.9, 0.35 + 0.08 * edge.pass_count)
        edge_intensity = min(1.0, edge.pass_count / pass_counts["pass_count"].max())
        edge_color = plt.cm.magma(edge_intensity)
        pitch.lines(
            origin["x"],
            origin["y"],
            target["x"],
            target["y"],
            color=edge_color,
            lw=width,
            alpha=alpha,
            ax=ax,
            zorder=3,
        )

    descriptor = dataset.descriptor if dataset else None

    title_parts: list[str] = []
    if descriptor:
        matchup = _matchup_label(descriptor.match)
        if matchup:
            title_parts.append(matchup)
    title_parts.append(f"{team_name} pass network")
    ax.set_title(" – ".join(title_parts), fontsize=14, color="#f3f5f4", weight="bold")

    output_dir_path = _ensure_output_dir(output_dir)
    if not filename:
        slug_team = _slug(team_name)
        match_id = descriptor.match_id if descriptor else "unknown"
        filename = f"pass-network_match-{match_id}_{slug_team}.png"
    output_path = output_dir_path / filename
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return PassNetworkResult(
        path=output_path,
        team_name=team_name,
        match_id=descriptor.match_id if descriptor else None,
        competition_id=descriptor.competition_id if descriptor else None,
        season_id=descriptor.season_id if descriptor else None,
        edge_count=len(pass_counts),
        node_count=len(nodes),
        total_passes=int(pass_counts["pass_count"].sum()),
    )


def _short_name(name: str) -> str:
    parts = (name or "").split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:10]
    return f"{parts[0][0]}. {parts[-1][:10]}"


def _matchup_label(match: Optional[dict]) -> Optional[str]:
    if not match:
        return None
    home = match.get("home_team", {}).get("home_team_name")
    away = match.get("away_team", {}).get("away_team_name")
    if home and away:
        return f"{home} vs {away}"
    return None


def _opponent_from_match(match: Optional[dict], team_name: Optional[str]) -> Optional[str]:
    if not match or not team_name:
        return None
    home = match.get("home_team", {}).get("home_team_name")
    away = match.get("away_team", {}).get("away_team_name")
    team_name_lower = team_name.lower()
    if home and team_name_lower == home.lower():
        return away
    if away and team_name_lower == away.lower():
        return home
    return None


def _slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _heatmap_title(team_name: Optional[str], descriptor: Optional[MatchDescriptor], event_types: Sequence[str]) -> str:
    segments: list[str] = []
    if descriptor:
        matchup = _matchup_label(descriptor.match)
        if matchup:
            segments.append(matchup)
    if team_name:
        segments.append(team_name)
    segments.append(f"{', '.join(event_types)} heatmap")
    return " – ".join(segments)
