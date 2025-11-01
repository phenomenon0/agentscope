from __future__ import annotations

import sqlite3
import sys
import types
from pathlib import Path

import pytest

if "agentscope" not in sys.modules:
    agentscope_package = types.ModuleType("agentscope")
    sys.modules["agentscope"] = agentscope_package
else:
    agentscope_package = sys.modules["agentscope"]

if "agentscope.tool" not in sys.modules:
    tool_module = types.ModuleType("agentscope.tool")

    class DummyToolkit:
        def __init__(self) -> None:
            self.groups: dict[str, list] = {}

        def create_tool_group(self, name: str, description: str | None = None, active: bool = True, **_kwargs) -> None:
            self.groups[name] = []

        def update_tool_groups(self, group_names, active: bool = True) -> None:  # pragma: no cover - placeholder
            pass

        def register_tool_function(self, func, group_name: str, func_description: str | None = None) -> None:
            self.groups.setdefault(group_name, []).append(func)

    class DummyToolResponse:
        def __init__(self, content, metadata=None) -> None:
            self.content = content
            self.metadata = metadata or {}

    tool_module.Toolkit = DummyToolkit
    tool_module.ToolResponse = DummyToolResponse
    sys.modules["agentscope.tool"] = tool_module
    agentscope_package.tool = tool_module

if "agentscope.message" not in sys.modules:
    message_module = types.ModuleType("agentscope.message")

    class DummyTextBlock(dict):
        def __init__(self, type: str, text: str) -> None:
            super().__init__(type=type, text=text)
            self.type = type
            self.text = text

    class DummyToolUseBlock(DummyTextBlock):
        pass

    class DummyImageBlock(DummyTextBlock):
        pass

    message_module.TextBlock = DummyTextBlock
    message_module.ToolUseBlock = DummyToolUseBlock
    message_module.ImageBlock = DummyImageBlock
    sys.modules["agentscope.message"] = message_module
    agentscope_package.message = message_module

if "agentscope.agent" not in sys.modules:
    agent_module = types.ModuleType("agentscope.agent")

    class DummyReActAgent:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - placeholder
            pass

        async def reply(self, *_args, **_kwargs):  # pragma: no cover
            raise RuntimeError("Dummy agent cannot reply")

    agent_module.ReActAgent = DummyReActAgent
    sys.modules["agentscope.agent"] = agent_module
    agentscope_package.agent = agent_module

if "agentscope.model" not in sys.modules:
    model_module = types.ModuleType("agentscope.model")

    class DummyModel:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            pass

    model_module.AnthropicChatModel = DummyModel
    model_module.OpenAIChatModel = DummyModel
    sys.modules["agentscope.model"] = model_module
    agentscope_package.model = model_module

if "agentscope.formatter" not in sys.modules:
    formatter_module = types.ModuleType("agentscope.formatter")

    class DummyFormatter:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            pass

    formatter_module.AnthropicChatFormatter = DummyFormatter
    formatter_module.OpenAIChatFormatter = DummyFormatter
    sys.modules["agentscope.formatter"] = formatter_module
    agentscope_package.formatter = formatter_module

if "agentscope.plan" not in sys.modules:
    plan_module = types.ModuleType("agentscope.plan")

    class DummyPlanNotebook:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover
            pass

    plan_module.PlanNotebook = DummyPlanNotebook
    sys.modules["agentscope.plan"] = plan_module
    agentscope_package.plan = plan_module

from agentspace.analytics import season_summary_store as store_module
from agentspace.analytics.season_summary_store import (
    CompetitionConfig,
    PositionBucketConfig,
    SeasonConfig,
    SeasonSummaryStore,
    ingest_competition_season,
)
from agentspace.agent_tools.rankings import (
    list_ranking_coverage_tool,
    list_ranking_metrics_tool,
    list_ranking_suites_tool,
    player_percentile_snapshot_tool,
    _parse_competition_filters,
    rank_players_by_metric_tool,
    rank_players_by_suite_tool,
)
from agentspace.api import leaderboards as leaderboard_service


@pytest.fixture()
def seeded_season_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "season_summaries.db"
    store = SeasonSummaryStore(db_path)
    competition = CompetitionConfig(
        name="Premier League",
        competition_id=2,
        seasons=(
            SeasonConfig(
                label="2025/2026",
                min_minutes=600,
                percentile_positions=(
                    PositionBucketConfig(
                        name="Forwards",
                        include=("Striker",),
                    ),
                ),
            ),
        ),
    )

    monkeypatch.setattr(store_module, "season_id_for_label", lambda *_args, **_kwargs: 501)

    fake_rows = [
        {
            "player_id": 101,
            "player_name": "Alice Smith",
            "team_id": 701,
            "team_name": "Arsenal",
            "position": "Striker",
            "primary_position": "Striker",
            "secondary_position": "Winger",
            "player_season_minutes": 1820,
            "player_season_goals_90": 0.60,
            "player_season_assists_90": 0.28,
            "player_season_shot_on_target_ratio": 0.55,
            "player_season_progressive_passes": 140,
            "player_season_progressive_passes_90": 5.4,
        },
        {
            "player_id": 102,
            "player_name": "Betty Jones",
            "team_id": 702,
            "team_name": "Chelsea",
            "position": "Striker",
            "primary_position": "Striker",
            "secondary_position": "Attacking Midfielder",
            "player_season_minutes": 1680,
            "player_season_goals_90": 0.42,
            "player_season_assists_90": 0.36,
            "player_season_shot_on_target_ratio": 0.47,
            "player_season_progressive_passes": 118,
            "player_season_progressive_passes_90": 4.7,
        },
        {
            "player_id": 103,
            "player_name": "Cara Lee",
            "team_id": 703,
            "team_name": "Everton",
            "position": "Midfield",
            "primary_position": "Central Midfielder",
            "secondary_position": "Defensive Midfielder",
            "player_season_minutes": 1945,
            "player_season_goals_90": 0.10,
            "player_season_assists_90": 0.55,
            "player_season_shot_on_target_ratio": 0.32,
            "player_season_progressive_passes": 96,
            "player_season_progressive_passes_90": 4.4,
        },
    ]

    def fake_fetch(*_args, **_kwargs):
        return fake_rows

    monkeypatch.setattr(store_module, "fetch_player_season_stats_data", fake_fetch)

    with store.connect() as conn:
        store.ensure_schema(conn)
        ingest_competition_season(store, conn, competition, competition.seasons[0], dry_run=False)

    return db_path


def test_ingestion_writes_percentiles(seeded_season_db: Path) -> None:
    conn = sqlite3.connect(seeded_season_db)
    try:
        count = conn.execute("SELECT COUNT(*) FROM player_season_summary").fetchone()[0]
        assert count == 3

        percentiles = conn.execute(
            """
            SELECT player_id, metric_name, percentile
              FROM player_metric_percentile
             WHERE metric_name = 'player_season_goals_90'
               AND cohort_key LIKE '%:all'
             ORDER BY player_id
            """
        ).fetchall()
        assert len(percentiles) == 3
        # Highest scorer should have percentile 100, lowest near 33.33
        pct_map = {row[0]: row[2] for row in percentiles}
        assert pct_map[101] == pytest.approx(100.0)
        assert pct_map[102] == pytest.approx((2 / 3) * 100, rel=1e-2)
        assert pct_map[103] == pytest.approx((1 / 3) * 100, rel=1e-2)
    finally:
        conn.close()


def test_rankings_tool_returns_leaderboard(seeded_season_db: Path) -> None:
    response = rank_players_by_metric_tool(
        metric_name="player_season_goals_90",
        season_label="2025/2026",
        competitions="2",
        limit=5,
        db_path=str(seeded_season_db),
    )
    assert response.metadata
    top_player = response.metadata["results"][0]
    assert top_player["player_name"] == "Alice Smith"
    assert top_player["percentile"] == pytest.approx(100.0)
    first_block = response.content[0]
    text = first_block.get("text") if isinstance(first_block, dict) else getattr(first_block, "text", "")
    assert "Leaderboard" in text


def test_rankings_tool_metric_alias(seeded_season_db: Path) -> None:
    response = rank_players_by_metric_tool(
        metric_name="progressive_passes",
        season_label="2025/2026",
        competitions="2",
        limit=3,
        db_path=str(seeded_season_db),
    )
    assert response.metadata["results"][0]["metric_value"] == pytest.approx(140)


def test_rankings_tool_shots_alias(seeded_season_db: Path) -> None:
    response = rank_players_by_metric_tool(
        metric_name="shots_on_target",
        season_label="2025/2026",
        competitions="2",
        db_path=str(seeded_season_db),
    )
    assert response.metadata["results"][0]["metric_value"] == pytest.approx(0.55)


def test_rank_players_by_suite_tool(seeded_season_db: Path) -> None:
    response = rank_players_by_suite_tool(
        metric_names="player_season_goals_90,player_season_assists_90",
        season_label="2025/2026",
        competitions="2",
        limit=3,
        db_path=str(seeded_season_db),
    )
    metadata = response.metadata
    assert metadata["metrics"] == [
        "player_season_goals_90",
        "player_season_assists_90",
    ]
    first = metadata["results"][0]
    assert "metrics" in first
    assert first["metrics"]["player_season_goals_90"]["value"] == pytest.approx(0.60)
    assert first["position_bucket"] == "ST"


def test_percentile_snapshot_tool_filters_player(seeded_season_db: Path) -> None:
    response = player_percentile_snapshot_tool(
        player_id=102,
        season_label="2025/2026",
        competition_id=2,
        limit=5,
        position_bucket="Forwards",
        db_path=str(seeded_season_db),
    )
    assert response.metadata["player_id"] == 102
    metrics = response.metadata["metrics"]
    assert any(item["metric"] == "player_season_goals_90" for item in metrics)
    first_block = response.content[0]
    text = first_block.get("text") if isinstance(first_block, dict) else getattr(first_block, "text", "")
    assert "Betty Jones" in text


def test_ranking_coverage_tool(seeded_season_db: Path) -> None:
    response = list_ranking_coverage_tool(db_path=str(seeded_season_db))
    assert response.metadata["results"]
    first = response.metadata["results"][0]
    assert first["season_label"] == "2025/2026"


def test_ranking_metrics_tool(seeded_season_db: Path) -> None:
    response = list_ranking_metrics_tool(season_label="2025/2026", competitions="2", db_path=str(seeded_season_db))
    metrics = response.metadata["metrics"]
    assert "player_season_goals_90" in metrics
    assert "player_season_progressive_passes" in metrics


def test_list_ranking_suites_tool() -> None:
    response = list_ranking_suites_tool()
    suites = response.metadata["suites"]
    assert "shooting" in suites
    assert "player_season_np_shots_90" in suites["shooting"]["metrics"]


def test_competition_alias_parsing() -> None:
    ids, names = _parse_competition_filters("Champions League")
    assert ids == [16]
    assert names == []


def test_rankings_tool_missing_metric(seeded_season_db: Path) -> None:
    response = rank_players_by_metric_tool(
        metric_name="nonexistent_metric",
        season_label="2025/2026",
        competitions="2",
        db_path=str(seeded_season_db),
    )
    assert response.metadata.get("error") == "missing_metric"


def test_leaderboard_api_endpoint(seeded_season_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTSPACE_SEASON_DB", str(seeded_season_db))
    text, metadata = leaderboard_service.get_player_leaderboard(
        metric_name="player_season_goals_90",
        season_label="2025/2026",
        competitions="2",
        limit=3,
        sort_order="desc",
        min_minutes=None,
        position_bucket=None,
    )
    data = {
        "table": text,
        "metadata": metadata,
    }
    assert data["metadata"]["metric"] == "player_season_goals_90"
    assert data["metadata"]["results"][0]["player_name"] == "Alice Smith"


def test_percentile_api_endpoint(seeded_season_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTSPACE_SEASON_DB", str(seeded_season_db))
    text, metadata = leaderboard_service.get_player_percentile_snapshot(
        season_label="2025/2026",
        player_id=101,
        player_name=None,
        competition_id=2,
        competitions=None,
        limit=4,
        position_bucket=None,
    )
    data = {
        "details": text,
        "metadata": metadata,
    }
    assert data["metadata"]["player_id"] == 101
    assert any(metric["metric"] == "player_season_goals_90" for metric in data["metadata"]["metrics"])
