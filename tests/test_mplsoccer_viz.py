"""
Tests for mplsoccer visualization helpers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Tuple

import numpy as np
import pandas as pd
import pytest

from agentspace.analytics import mplsoccer_viz as viz


class DummyFig:
    def __init__(self) -> None:
        self.facecolor = "#ffffff"

    def set_facecolor(self, color: str) -> None:
        self.facecolor = color

    def savefig(self, path: Path | str, **_: Any) -> None:
        Path(path).write_bytes(b"png")

    def get_facecolor(self) -> str:
        return self.facecolor


class DummyAx:
    def set_title(self, *_: Any, **__: Any) -> None:
        return None

    def legend(self, *_: Any, **__: Any) -> None:
        return None

    def text(self, *_: Any, **__: Any) -> None:
        return None


class DummyPitch:
    def __init__(self, **_: Any) -> None:
        pass

    def draw(self, **_: Any) -> Tuple[DummyFig, DummyAx]:
        return DummyFig(), DummyAx()

    def scatter(self, *_: Any, **__: Any) -> None:
        return None

    def bin_statistic(self, *_, bins: Tuple[int, int], **__: Any) -> dict[str, Any]:
        return {"statistic": np.zeros(bins)}

    def heatmap(self, *_: Any, **__: Any) -> None:
        return None

    def lines(self, *_: Any, **__: Any) -> None:
        return None


class DummyPlt:
    class _CM:
        def viridis(self, values):
            arr = np.atleast_1d(values)
            return np.tile(np.array([0.1, 0.2, 0.3, 1.0]), (arr.size, 1))

        def magma(self, values):
            arr = np.atleast_1d(values)
            return np.tile(np.array([0.3, 0.1, 0.4, 1.0]), (arr.size, 1))

    cm = _CM()

    @staticmethod
    def close(_fig: Any) -> None:
        return None


@pytest.fixture(autouse=True)
def _patch_mplsoccer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(viz, "_load_mplsoccer", lambda: (DummyPitch, DummyPlt))


def test_plot_match_shot_map_from_dataframe(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "event_type": "Shot",
                "team": "Arsenal",
                "location_x": 0.8,
                "location_y": 0.5,
                "shot_outcome": "Goal",
                "shot_xg": 0.32,
            },
            {
                "event_type": "Shot",
                "team": "Chelsea",
                "location_x": 0.5,
                "location_y": 0.3,
                "shot_outcome": "Saved",
                "shot_xg": 0.12,
            },
        ]
    )

    result = viz.plot_match_shot_map(
        df,
        team_name="Arsenal",
        output_dir=tmp_path,
        filename="shot-map.png",
    )

    assert result.total_shots == 1
    assert result.total_goals == 1
    assert result.opponent_shots == 1
    assert result.path == tmp_path / "shot-map.png"
    assert result.path.exists()


def test_plot_event_heatmap(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "event_type": "Pass",
                "team": "Arsenal",
                "location_x": 60.0,
                "location_y": 40.0,
            },
            {
                "event_type": "Carry",
                "team": "Arsenal",
                "location_x": 55.0,
                "location_y": 38.0,
            },
        ]
    )

    result = viz.plot_event_heatmap(
        df,
        team_name="Arsenal",
        event_types=("Pass", "Carry"),
        bins=(12, 8),
        output_dir=tmp_path,
        filename="heatmap.png",
    )

    assert result.sample_size == 2
    assert result.path == tmp_path / "heatmap.png"
    assert result.path.exists()


def test_plot_pass_network(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "event_type": "Pass",
                "team": "Arsenal",
                "player_id": 1,
                "player_name": "Martin Odegaard",
                "location_x": 40.0,
                "location_y": 35.0,
                "pass_end_x": 55.0,
                "pass_end_y": 38.0,
                "pass_outcome": "Complete",
                "pass_recipient_id": 2,
                "pass_recipient_name": "Bukayo Saka",
            },
            {
                "event_type": "Pass",
                "team": "Arsenal",
                "player_id": 1,
                "player_name": "Martin Odegaard",
                "location_x": 42.0,
                "location_y": 36.0,
                "pass_end_x": 58.0,
                "pass_end_y": 34.0,
                "pass_outcome": "Complete",
                "pass_recipient_id": 2,
                "pass_recipient_name": "Bukayo Saka",
            },
            {
                "event_type": "Pass",
                "team": "Arsenal",
                "player_id": 2,
                "player_name": "Bukayo Saka",
                "location_x": 60.0,
                "location_y": 30.0,
                "pass_end_x": 48.0,
                "pass_end_y": 32.0,
                "pass_outcome": "Complete",
                "pass_recipient_id": 1,
                "pass_recipient_name": "Martin Odegaard",
            },
        ]
    )

    result = viz.plot_pass_network(
        df,
        team_name="Arsenal",
        min_pass_count=1,
        output_dir=tmp_path,
        filename="pass-network.png",
    )

    assert result.edge_count == 2
    assert result.node_count == 2
    assert result.total_passes == 3
    assert result.path == tmp_path / "pass-network.png"
    assert result.path.exists()
