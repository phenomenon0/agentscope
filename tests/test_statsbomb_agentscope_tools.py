from __future__ import annotations

from dataclasses import dataclass

import pytest

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
    assert "compare_player_season_summaries_tool" in toolkit.tools


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
