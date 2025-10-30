from __future__ import annotations

from dataclasses import dataclass

import pytest
import pandas as pd

from agentscope.tool import Toolkit

from agentspace.agent_tools import statsbomb as tools
from agentspace.services.statsbomb_tools import (
    EventContext,
    MatchDataset,
    MatchDescriptor,
    PlayerEventSummary,
)


def _sample_match() -> dict:
    return {
        "match_id": 1,
        "match_date": "2024-12-14",
        "competition": {"competition_name": "Premier League"},
        "season": {"season_name": "2024/2025"},
        "home_team": {"home_team_name": "Arsenal"},
        "away_team": {"away_team_name": "Everton"},
        "match_status": "played",
    }


def test_list_team_matches(monkeypatch):
    descriptor = MatchDescriptor(
        match_id=1,
        competition_id=2,
        season_id=317,
        match=_sample_match(),
    )
    monkeypatch.setattr(
        tools,
        "find_matches_for_team",
        lambda **_: [descriptor],
    )

    response = tools.list_team_matches("Arsenal", opponent_name="Everton")

    assert response.metadata is not None
    matches = response.metadata["matches"]
    assert matches[0]["match_id"] == 1
    assert "Arsenal" in response.content[0]["text"]


def test_list_competitions_tool(monkeypatch):
    competitions = [
        {
            "competition_id": 2,
            "competition_name": "Premier League",
            "season_id": 317,
        }
    ]
    monkeypatch.setattr(tools, "list_competitions", lambda **_: competitions)
    response = tools.list_competitions_tool(name="Premier")
    assert response.metadata["competitions"] == competitions
    assert "Found 1" in response.content[0]["text"]


def test_list_seasons_tool(monkeypatch):
    seasons = [{"season_id": 317, "season_name": "2024/2025"}]
    monkeypatch.setattr(
        tools,
        "list_seasons",
        lambda competition_id, **_: seasons,
    )
    response = tools.list_seasons_tool(competition_id=2)
    assert response.metadata["seasons"] == seasons
    assert "competition 2" in response.content[0]["text"]


def test_count_player_passes_by_body_part_tool(monkeypatch):
    descriptor = MatchDescriptor(
        match_id=1,
        competition_id=2,
        season_id=317,
        match=_sample_match(),
    )

    monkeypatch.setattr(
        tools,
        "find_matches_for_team",
        lambda **_: [descriptor],
    )

    monkeypatch.setattr(
        tools,
        "count_player_passes_by_body_part",
        lambda descriptors, **_: PlayerEventSummary(total=3, by_match={1: 3}),
    )

    response = tools.count_player_passes_by_body_part_tool(
        "Bukayo Saka",
        "Left Foot",
        team_name="Arsenal",
    )

    assert response.metadata["total_passes"] == 3
    assert "Left Foot" in response.content[0]["text"]


def test_fetch_match_events(monkeypatch):
    match = _sample_match()
    descriptor = MatchDescriptor(
        match_id=1,
        competition_id=2,
        season_id=317,
        match=match,
    )
    event = {
        "id": "evt-1",
        "type": {"name": "Pass"},
        "team": {"name": "Arsenal"},
        "player": {"name": "Bukayo Saka"},
        "minute": 5,
        "second": 30.0,
    }
    context = EventContext(
        event=event,
        match=match,
        home_score=0,
        away_score=0,
        score_state="level",
        elapsed_seconds=330.0,
    )
    dataset = MatchDataset(
        descriptor=descriptor,
        match=match,
        events=[context],
        lineups=[{"team": "Arsenal"}],
        frames=None,
    )

    monkeypatch.setattr(tools, "fetch_match_dataset", lambda *_, **__: dataset)

    response = tools.fetch_match_events(1, competition_id=2, season_id=317)

    assert response.metadata["preview_events"][0]["event_id"] == "evt-1"
    assert "Retrieved" in response.content[0]["text"]


def test_fetch_match_events_extended_filters(monkeypatch):
    match = _sample_match()
    descriptor = MatchDescriptor(
        match_id=2,
        competition_id=2,
        season_id=317,
        match=match,
    )

    captured = {}

    def fake_fetch_match_dataset(descriptor_arg, *, filters, **kwargs):
        captured["filters"] = filters
        return MatchDataset(descriptor_arg, match, [], None, None)

    monkeypatch.setattr(tools, "fetch_match_dataset", fake_fetch_match_dataset)

    response = tools.fetch_match_events(
        descriptor.match_id,
        descriptor.competition_id,
        descriptor.season_id,
        team_name="Arsenal",
        event_types=["Pass"],
        player_names=["Bukayo Saka"],
        possession_team_names=["Arsenal"],
        periods=[1],
        minute_range=[0, 45],
        time_range=[0.0, 2700.0],
        score_states=["leading"],
        play_patterns=["From Open Play"],
        outcome_names=["Complete"],
        zone="final_third",
    )

    filters = captured["filters"]
    assert filters.team_names == ["Arsenal"]
    assert filters.possession_team_names == ["Arsenal"]
    assert filters.event_types == ["Pass"]
    assert filters.player_names == ["Bukayo Saka"]
    assert filters.play_patterns == ["From Open Play"]
    assert filters.outcome_names == ["Complete"]
    assert filters.minute_range == (0, 45)
    assert filters.time_range == (0.0, 2700.0)
    assert filters.zone == "final_third"
    assert "Retrieved" in response.content[0]["text"]


def test_fetch_player_season_aggregates(monkeypatch):
    records = [{"player_name": "Bukayo Saka", "player_season_minutes": 900}]
    monkeypatch.setattr(
        tools,
        "fetch_player_season_stats_data",
        lambda *_, **__: records,
    )
    response = tools.fetch_player_season_aggregates(2, 317)
    assert response.metadata["records"] == records


def test_fetch_team_season_aggregates(monkeypatch):
    records = [{"team_name": "Arsenal"}]
    monkeypatch.setattr(
        tools,
        "fetch_team_season_stats_data",
        lambda *_, **__: records,
    )
    response = tools.fetch_team_season_aggregates(2, 317)
    assert response.metadata["records"] == records


def test_fetch_player_match_aggregates(monkeypatch):
    rows = [{"player_name": "Bukayo Saka", "match_id": 1}]
    monkeypatch.setattr(
        tools,
        "fetch_player_match_stats_data",
        lambda *_, **__: rows,
    )
    response = tools.fetch_player_match_aggregates(1)
    assert response.metadata["records"] == rows


def test_list_team_players_tool(monkeypatch):
    monkeypatch.setattr(tools, "resolve_competition_id", lambda _: 2)
    monkeypatch.setattr(
        tools,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    players = [
        {
            "player_id": 1,
            "player_name": "Bukayo Saka",
            "team_name": "Arsenal",
            "position": "FW",
            "player_season_minutes": 900,
            "player_season_goals": 10,
            "player_season_assists": 7,
        },
        {
            "player_id": 2,
            "player_name": "Declan Rice",
            "team_name": "Arsenal",
            "position": "MF",
            "player_season_minutes": 1100,
            "player_season_goals": 5,
            "player_season_assists": 6,
        },
    ]

    monkeypatch.setattr(
        tools,
        "get_competition_players",
        lambda **_: players,
    )

    response = tools.list_team_players_tool(
        "Arsenal",
        "2024/2025",
        competition="Premier League",
    )

    assert response.metadata["team_name"] == "Arsenal"
    assert response.metadata["players"] == players
    assert "Found 2 player(s)" in response.content[0]["text"]


def test_list_competition_players_tool(monkeypatch):
    monkeypatch.setattr(tools, "resolve_competition_id", lambda _: 2)
    monkeypatch.setattr(
        tools,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    players = [
        {
            "player_id": 3,
            "player_name": "Cole Palmer",
            "team_name": "Chelsea",
            "position": "FW",
            "player_season_minutes": 800,
            "player_season_goals": 9,
            "player_season_assists": 5,
        }
    ]

    monkeypatch.setattr(
        tools,
        "get_competition_players",
        lambda **_: players,
    )

    response = tools.list_competition_players_tool(
        "2024/2025",
        competition="Premier League",
        team_name="Chelsea",
    )

    assert response.metadata["competition_id"] == 2
    assert response.metadata["players"] == players
    assert "Found 1 player(s) for Chelsea" in response.content[0]["text"]


def test_summarise_match_performance(monkeypatch):
    match = _sample_match()
    descriptor = MatchDescriptor(
        match_id=1,
        competition_id=2,
        season_id=317,
        match=match,
    )

    dataset = MatchDataset(descriptor=descriptor, match=match, events=[])

    monkeypatch.setattr(tools, "fetch_match_dataset", lambda *_, **__: dataset)
    monkeypatch.setattr(tools, "events_to_dataframe", lambda *_: pd.DataFrame({"event_type": []}))

    player_summary_df = pd.DataFrame(
        [
            {
                "match_id": 1,
                "player_id": 10,
                "player_name": "Bukayo Saka",
                "team": "Arsenal",
                "goals": 1,
                "xg": 0.4,
                "progressive_actions": 5,
                "passes_attempted": 30,
                "passes_completed": 25,
                "shots_total": 3,
            }
        ]
    )

    team_summary_df = pd.DataFrame(
        [
            {
                "match_id": 1,
                "team": "Arsenal",
                "match_date": "2024-08-10",
                "opponent": "Manchester United",
                "goals": 2,
                "xg": 1.5,
                "passes_completed": 500,
            }
        ]
    )

    leaderboard_table = pd.DataFrame(
        [{"player_name": "Bukayo Saka", "team": "Arsenal", "goals": 1}]
    )

    monkeypatch.setattr(tools, "summarise_player_events", lambda *_: player_summary_df)
    monkeypatch.setattr(tools, "summarise_team_events", lambda *_: team_summary_df)
    monkeypatch.setattr(
        tools,
        "build_player_leaderboards",
        lambda *_ , **__: {"shooting": {"goals": leaderboard_table}},
    )

    response = tools.summarise_match_performance(
        1,
        competition_id=2,
        season_id=317,
        top_n=3,
    )

    assert response.metadata["player_summary"][0]["player_name"] == "Bukayo Saka"
    assert response.metadata["team_summary"][0]["team"] == "Arsenal"
    assert "Leaderboard highlights" in response.content[0]["text"]


def test_player_season_summary_tool(monkeypatch):
    summary = {
        "player_name": "Bukayo Saka",
        "team_name": "Arsenal",
        "player_season_minutes": 900,
    }

    monkeypatch.setattr(tools, "resolve_competition_id", lambda name: 2)
    monkeypatch.setattr(
        tools,
        "get_player_season_summary",
        lambda **_: summary,
    )

    response = tools.player_season_summary_tool(
        "Bukayo Saka",
        "2024/2025",
        competition="Premier League",
    )

    assert response.metadata["record"]["player_name"] == "Bukayo Saka"


def test_player_season_summary_tool_uses_resolver(monkeypatch):
    calls = {"attempts": 0}

    def fake_get_player_season_summary(**kwargs):
        if calls["attempts"] == 0:
            calls["attempts"] += 1
            raise ValueError("No records returned")
        return {
            "player_name": "Scott McTominay",
            "team_name": "Manchester United",
            "player_season_minutes": 1500,
            "season_name": "2024/2025",
            "competition_id": 2,
        }

    monkeypatch.setattr(tools, "resolve_competition_id", lambda name: 2)
    monkeypatch.setattr(tools, "get_player_season_summary", fake_get_player_season_summary)
    monkeypatch.setattr(
        tools,
        "resolve_player_current_team",
        lambda *_, **__: (
            {
                "player_name": "Scott McTominay",
                "team_name": "Manchester United",
                "competition_id": 2,
                "season_label": "2024/2025",
            },
            [],
        ),
    )

    response = tools.player_season_summary_tool(
        "Scott McTominay",
        "2025/2026",
        competition="Premier League",
    )

    assert response.metadata["record"]["player_name"] == "Scott McTominay"
    assert response.metadata["resolver"] is not None


def test_resolve_player_current_team_tool(monkeypatch):
    best = {
        "player_name": "Bukayo Saka",
        "player_id": 1,
        "team_name": "Arsenal",
        "competition_id": 2,
        "season_label": "2024/2025",
        "player_season_minutes": 2200.0,
    }
    candidates = [best]
    monkeypatch.setattr(
        tools,
        "resolve_player_current_team",
        lambda *args, **kwargs: (best, candidates),
    )

    response = tools.resolve_player_current_team_tool(
        "Bukayo Saka",
        season_label="2024/2025",
        competition_ids=[2],
    )

    assert "Arsenal" in response.content[0]["text"]
    assert response.metadata["best_match"]["team_name"] == "Arsenal"


def test_team_season_summary_tool(monkeypatch):
    summary = {
        "team_name": "Arsenal",
        "team_season_goals": 70,
    }

    monkeypatch.setattr(tools, "resolve_competition_id", lambda name: 2)
    monkeypatch.setattr(
        tools,
        "get_team_season_summary",
        lambda **_: summary,
    )

    response = tools.team_season_summary_tool(
        "Arsenal",
        "2024/2025",
        competition="Premier League",
    )

    assert response.metadata["record"]["team_name"] == "Arsenal"


def test_player_multi_season_summary_tool(monkeypatch):
    summaries = {
        "2023/2024": {"season_label": "2023/2024", "player_name": "Bukayo Saka"},
        "2024/2025": {"season_label": "2024/2025", "player_name": "Bukayo Saka"},
    }

    monkeypatch.setattr(tools, "resolve_competition_id", lambda name: 2)
    monkeypatch.setattr(
        tools,
        "get_player_season_summary",
        lambda player_name, season_label, competition_id, **_: summaries[season_label],
    )

    response = tools.player_multi_season_summary_tool(
        "Bukayo Saka",
        ["2023/2024", "2024/2025"],
        competition="Premier League",
    )

    assert len(response.metadata["records"]) == 2


def test_compare_player_season_summaries_tool(monkeypatch):
    summaries = {
        "Bukayo Saka": {"player_name": "Bukayo Saka", "team_name": "Arsenal"},
        "Gabriel Jesus": {"player_name": "Gabriel Jesus", "team_name": "Arsenal"},
    }

    monkeypatch.setattr(tools, "resolve_competition_id", lambda name: 2)
    monkeypatch.setattr(
        tools,
        "get_players_season_summary",
        lambda **_: (summaries, []),
    )

    response = tools.compare_player_season_summaries_tool(
        ["Bukayo Saka", "Gabriel Jesus"],
        "2024/2025",
        competition="Premier League",
    )

    assert set(response.metadata["records"].keys()) == {"Bukayo Saka", "Gabriel Jesus"}


def test_player_report_template_tool_defaults():
    response = tools.player_report_template_tool()
    template = response.metadata["template"]
    assert template["executive_summary"]["player"] == "[PLAYER_NAME]"
    module = template["key_skill_analysis"][0]
    assert module["module_title"].startswith("Module 1")
    assert module["metrics_table"]["columns"] == ["Metric", "Value", "Percentile", "Context"]
    assert module["metrics_table"]["rows"][0]["metric"] == "Tackles"
    assert template["key_skill_analysis"][0]["summary"] == "[AI_GENERATED_SUMMARY_OF_SKILL_1]"
    assert response.content[0]["text"].strip().startswith("{")


def test_register_statsbomb_tools_creates_group(monkeypatch):
    toolkit = Toolkit()
    monkeypatch.setattr(
        tools,
        "find_matches_for_team",
        lambda **_: [],
    )
    monkeypatch.setattr(
        tools,
        "count_player_passes_by_body_part",
        lambda *_, **__: PlayerEventSummary(total=0, by_match={}),
    )
    monkeypatch.setattr(
        tools,
        "fetch_match_dataset",
        lambda *_, **__: MatchDataset(
            descriptor=MatchDescriptor(match_id=1, competition_id=1, season_id=1),
            match={},
            events=[],
        ),
    )

    toolkit = tools.register_statsbomb_tools(toolkit)

    # Toolkit now knows about our functions
    registered = set(toolkit.tools)
    assert "compare_player_season_summaries_tool" in registered
    assert "player_report_template_tool" in registered


def test_init_session_with_statsbomb_tools(monkeypatch):
    called = {}

    def fake_init(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(tools.agentscope, "init", fake_init)
    monkeypatch.setattr(
        tools,
        "register_statsbomb_tools",
        lambda **kwargs: kwargs,
    )

    result = tools.init_session_with_statsbomb_tools(
        project="proj", name="run", logging_level="DEBUG", activate=False
    )

    assert called["project"] == "proj"
    assert result["activate"] is False
