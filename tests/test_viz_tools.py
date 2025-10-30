"""
Tests for visualization agent tools.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentscope.tool import ToolResponse

from agentspace.agent_tools import viz as viz_tools
from agentspace.analytics.mplsoccer_viz import HeatmapResult, ShotMapResult, PassNetworkResult


def test_plot_match_shot_map_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dummy_dataset = object()
    output_path = tmp_path / "shot.png"
    output_path.write_bytes(b"shot")

    monkeypatch.setattr(viz_tools, "fetch_match_dataset", lambda *_args, **_kwargs: dummy_dataset)
    monkeypatch.setattr(
        viz_tools,
        "plot_match_shot_map",
        lambda data, **_: ShotMapResult(
            path=output_path,
            team_name="Arsenal",
            opponent_name="Chelsea",
            match_id=1,
            competition_id=2,
            season_id=281,
            total_shots=10,
            total_goals=3,
            opponent_shots=8,
            opponent_goals=1,
        ),
    )

    response = viz_tools.plot_match_shot_map_tool(
        match_id=1,
        competition_id=2,
        season_id=281,
        team_name="Arsenal",
        include_opponent=True,
        output_dir=str(tmp_path),
    )

    assert isinstance(response, ToolResponse)
    assert "Shots:" in response.content[0]["text"]
    assert response.metadata["image_path"] == str(output_path)
    assert response.metadata["total_shots"] == 10
    assert response.metadata["opponent_shots"] == 8
    assert response.content[1]["type"] == "image"
    assert response.content[1]["source"]["type"] == "base64"


def test_plot_event_heatmap_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dummy_dataset = object()
    heatmap_path = tmp_path / "heatmap.png"
    heatmap_path.write_bytes(b"heat")

    monkeypatch.setattr(viz_tools, "fetch_match_dataset", lambda *_args, **_kwargs: dummy_dataset)
    monkeypatch.setattr(
        viz_tools,
        "plot_event_heatmap",
        lambda data, **_: HeatmapResult(
            path=heatmap_path,
            team_name="Arsenal",
            event_types=("Pass", "Carry"),
            match_id=1,
            competition_id=2,
            season_id=281,
            sample_size=42,
        ),
    )

    response = viz_tools.plot_event_heatmap_tool(
        match_id=1,
        team_name="Arsenal",
        competition_id=2,
        season_id=281,
        event_types=("Pass", "Carry"),
        output_dir=str(tmp_path),
    )

    assert response.metadata["image_path"] == str(heatmap_path)
    assert response.metadata["sample_size"] == 42
    assert "heatmap" in response.metadata["viz_type"]
    assert response.content[1]["type"] == "image"
    assert response.content[1]["source"]["type"] == "base64"


def test_plot_pass_network_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dummy_dataset = object()
    network_path = tmp_path / "network.png"
    network_path.write_bytes(b"net")

    monkeypatch.setattr(viz_tools, "fetch_match_dataset", lambda *_args, **_kwargs: dummy_dataset)
    monkeypatch.setattr(
        viz_tools,
        "plot_pass_network",
        lambda data, **_: PassNetworkResult(
            path=network_path,
            team_name="Arsenal",
            match_id=1,
            competition_id=2,
            season_id=281,
            edge_count=5,
            node_count=7,
            total_passes=42,
        ),
    )

    response = viz_tools.plot_pass_network_tool(
        match_id=1,
        team_name="Arsenal",
        competition_id=2,
        season_id=281,
        min_pass_count=2,
        output_dir=str(tmp_path),
    )

    assert response.metadata["image_path"] == str(network_path)
    assert response.metadata["edge_count"] == 5
    assert response.metadata["node_count"] == 7
    assert response.metadata["total_passes"] == 42
    assert response.content[1]["type"] == "image"
    assert response.content[1]["source"]["type"] == "base64"


def test_plot_match_shot_map_tool_handles_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(viz_tools, "fetch_match_dataset", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(viz_tools, "plot_match_shot_map", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    response = viz_tools.plot_match_shot_map_tool(match_id=1)

    assert "Failed to render shot map" in response.content[0]["text"]
    assert response.metadata["error"].startswith("Failed to render shot map")
