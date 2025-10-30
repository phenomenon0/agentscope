from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from agentspace.services import statsbomb_tools as tools
from agentspace.services.statsbomb_tools import (
    EventContext,
    EventFilters,
    MatchDataset,
    MatchDescriptor,
    PlayerEventSummary,
    count_player_passes_by_body_part,
    find_matches_for_team,
    list_matches,
    resolve_competition_id,
    season_id_for_label,
    get_player_season_summary,
    get_team_season_summary,
    get_player_multi_season_summary,
    get_players_season_summary,
    get_competition_players,
    POPULAR_COMPETITIONS,
)


def _sample_match() -> Dict[str, Any]:
    return {
        "match_id": 1,
        "home_team": {"home_team_name": "Arsenal"},
        "away_team": {"away_team_name": "Chelsea"},
    }


def _sample_events() -> List[Dict[str, Any]]:
    return [
        {
            "id": 1,
            "type": {"name": "Pass"},
            "team": {"name": "Arsenal"},
            "player": {"name": "Bukayo Saka"},
            "minute": 5,
            "second": 10.0,
            "period": 1,
            "location": [50, 30],
            "play_pattern": {"name": "From Open Play"},
        },
        {
            "id": 2,
            "type": {"name": "Shot"},
            "team": {"name": "Chelsea"},
            "player": {"name": "Cole Palmer"},
            "minute": 10,
            "second": 5.0,
            "period": 1,
            "location": [20, 40],
            "shot": {"outcome": {"name": "Goal"}},
            "play_pattern": {"name": "From Open Play"},
        },
        {
            "id": 3,
            "type": {"name": "Pass"},
            "team": {"name": "Arsenal"},
            "player": {"name": "Martin Ødegaard"},
            "minute": 15,
            "second": 0.0,
            "period": 1,
            "location": [90, 20],
            "play_pattern": {"name": "From Counter"},
        },
    ]


def test_apply_filters_supports_game_state_and_zone():
    match = _sample_match()
    events = _sample_events()

    contexts = tools.apply_filters(events, match, None)
    assert [isinstance(ctx, EventContext) for ctx in contexts]
    assert len(contexts) == 3
    assert contexts[2].away_score == 1
    assert contexts[2].score_state == "trailing"

    trailing = tools.apply_filters(
        events,
        match,
        EventFilters(team_names=["Arsenal"], score_states=["trailing"]),
    )
    assert [ctx.event["id"] for ctx in trailing] == [3]

    final_third = tools.apply_filters(
        events,
        match,
        EventFilters(team_names=["Chelsea"], zone="final_third"),
    )
    assert [ctx.event["id"] for ctx in final_third] == [2]

    within_ten_minutes = tools.apply_filters(
        events,
        match,
        EventFilters(time_range=(0, 600)),
    )
    assert [ctx.event["id"] for ctx in within_ten_minutes] == [1]


def test_list_matches_returns_empty_on_missing():
    class DummyClient:
        def list_matches(self, *_args, **_kwargs):
            raise tools.APINotFoundError("missing")

    with patch.object(tools, "get_statsbomb_client", return_value=DummyClient()):
        matches = tools.list_matches(1, 2)
        assert matches == []


def test_list_matches_status_synonyms(monkeypatch):
    class DummyClient:
        def list_matches(self, *_args, **_kwargs):
            return [
                {
                    "match_id": 1,
                    "match_status": "available",
                    "home_team": {"home_team_name": "Arsenal"},
                    "away_team": {"away_team_name": "Manchester United"},
                },
                {
                    "match_id": 2,
                    "match_status": "scheduled",
                    "home_team": {"home_team_name": "Manchester United"},
                    "away_team": {"away_team_name": "Arsenal"},
                },
            ]

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())

    matches = tools.list_matches(
        2,
        317,
        team_name="Arsenal",
        opponent_name="Manchester United",
        match_status=["played"],
    )
    assert [match["match_id"] for match in matches] == [1]


def test_resolve_player_current_team(monkeypatch):
    tools._player_index_cache.clear()
    monkeypatch.setattr(
        tools,
        "_current_season_label",
        lambda: "2024/2025",
    )
    monkeypatch.setattr(
        tools,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    rows = [
        {
            "player_id": 1,
            "player_name": "Bukayo Saka",
            "team_name": "Arsenal",
            "player_season_minutes": 2000,
        },
        {
            "player_id": 2,
            "player_name": "Bukayo Saka",
            "team_name": "England",
            "player_season_minutes": 300,
        },
    ]

    monkeypatch.setattr(
        tools,
        "fetch_player_season_stats_data",
        lambda *_, **__: rows,
    )

    best, candidates = tools.resolve_player_current_team(
        "Bukayo Saka",
        season_label="2024/2025",
        competition_ids=[2],
        use_index=False,
    )

    assert best is not None
    assert best["team_name"] == "Arsenal"
    assert len(candidates) == 2


def test_resolve_player_current_team_respects_min_minutes(monkeypatch):
    tools._player_index_cache.clear()
    monkeypatch.setattr(
        tools,
        "_current_season_label",
        lambda: "2024/2025",
    )
    monkeypatch.setattr(
        tools,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    rows = [
        {
            "player_id": 1,
            "player_name": "Rasmus Hojlund",
            "team_name": "Manchester United",
            "player_season_minutes": 1500,
        },
        {
            "player_id": 2,
            "player_name": "Rasmus Hojlund",
            "team_name": "Atalanta",
            "player_season_minutes": 100,
        },
    ]

    monkeypatch.setattr(
        tools,
        "fetch_player_season_stats_data",
        lambda *_, **__: rows,
    )

    best, candidates = tools.resolve_player_current_team(
        "Rasmus Højlund",
        competition_ids=[2],
        min_minutes=200,
        season_label="2024/2025",
        use_index=False,
    )

    assert best["team_name"] == "Manchester United"
    assert len(candidates) == 1


def test_resolve_player_current_team_fallback_previous_season(monkeypatch):
    tools._player_index_cache.clear()

    monkeypatch.setattr(tools, "_current_season_label", lambda: "2025/2026")

    def fake_season_id(comp_id, label, use_cache=True):
        if label == "2025/2026":
            return 400
        if label == "2024/2025":
            return 317
        return None

    monkeypatch.setattr(tools, "season_id_for_label", fake_season_id)

    def fake_fetch(competition_id, season_id, **_):
        if season_id == 400:
            return []
        return [
            {
                "player_id": 1,
                "player_name": "Scott McTominay",
                "team_name": "Manchester United",
                "player_season_minutes": 1800,
            }
        ]

    monkeypatch.setattr(tools, "fetch_player_season_stats_data", fake_fetch)

    best, candidates = tools.resolve_player_current_team(
        "Scott McTominay",
        competition_ids=[2],
        season_label="2025/2026",
        use_index=False,
    )

    assert best["season_label"] == "2024/2025"
    assert best["team_name"] == "Manchester United"


def test_resolve_player_current_team_team_hint(monkeypatch):
    tools._player_index_cache.clear()
    monkeypatch.setattr(tools, "_current_season_label", lambda: "2024/2025")
    monkeypatch.setattr(
        tools,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    rows = [
        {
            "player_id": 1,
            "player_name": "Scott McTominay",
            "team_name": "Manchester United",
            "player_season_minutes": 1500,
        },
        {
            "player_id": 2,
            "player_name": "Scott McTominay",
            "team_name": "Scotland",
            "player_season_minutes": 500,
        },
    ]

    monkeypatch.setattr(tools, "fetch_player_season_stats_data", lambda *_, **__: rows)

    best, candidates = tools.resolve_player_current_team(
        "Scott McTominay",
        competition_ids=[2],
        team_name="Manchester United",
        use_index=False,
    )

    assert best["team_name"] == "Manchester United"


def test_get_player_season_summary_uses_resolver(monkeypatch):
    monkeypatch.setattr(
        tools,
        "resolve_player_current_team",
        lambda *_, **__: ({"competition_id": 2, "season_label": "2024/2025"}, []),
    )

    class DummyClient:
        def get_player_season_stats(self, *_, **__):
            return [
                {
                    "player_name": "Scott McTominay",
                    "team_name": "Manchester United",
                    "player_season_minutes": 1200,
                }
            ]

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())
    monkeypatch.setattr(
        tools,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    summary = tools.get_player_season_summary(
        player_name="Scott McTominay",
        season_label="2025/2026",
        competition_name=None,
        competition_id=None,
    )

    assert summary["team_name"] == "Manchester United"


def test_fetch_player_season_stats_handles_404(monkeypatch):
    class DummyClient:
        def get_player_season_stats(self, *_, **__):
            raise tools.APINotFoundError("missing")

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())
    rows = tools.fetch_player_season_stats_data(9, 999)
    assert rows == []


def test_fetch_team_season_stats_handles_404(monkeypatch):
    class DummyClient:
        def get_team_season_stats(self, *_, **__):
            raise tools.APINotFoundError("missing")

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())
    rows = tools.fetch_team_season_stats_data(9, 999)
    assert rows == []


def test_fetch_match_dataset_combines_components(monkeypatch):
    @dataclass
    class DummyClient:
        competitions: Dict[str, Any]
        seasons: Dict[str, Any]
        match: Dict[str, Any]
        events: List[Dict[str, Any]]

        def list_matches(self, *_args, **_kwargs):
            return [self.match]

        def get_events(self, *_args, **_kwargs):
            return self.events

        def get_lineups(self, *_args, **_kwargs):
            return [{"team": "Arsenal"}]

        def get_360_frames(self, *_args, **_kwargs):
            return [{"event_uuid": "abc"}]

    dummy = DummyClient({}, {}, _sample_match(), _sample_events())
    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: dummy)
    tools._match_index.cache_clear()

    descriptor = MatchDescriptor(
        match_id=_sample_match()["match_id"],
        competition_id=2,
        season_id=318,
    )
    dataset = tools.fetch_match_dataset(
        descriptor,
        filters=EventFilters(event_types=["Pass"]),
        include_lineups=True,
        include_frames=True,
        use_cache=False,
    )

    assert isinstance(dataset, MatchDataset)
    assert [ctx.event["id"] for ctx in dataset.events] == [1, 3]
    assert dataset.lineups == [{"team": "Arsenal"}]
    assert dataset.frames == [{"event_uuid": "abc"}]


def test_find_matches_for_team_filters(monkeypatch):
    competitions = [
        {"competition_id": 2, "season_id": 317, "season_name": "2024/2025"},
        {"competition_id": 3, "season_id": 500, "season_name": "2024/2025"},
    ]
    matches_lookup = {
        (2, 317): [
            {
                "match_id": 101,
                "home_team": {"home_team_name": "Arsenal"},
                "away_team": {"away_team_name": "Everton"},
            },
            {
                "match_id": 102,
                "home_team": {"home_team_name": "Arsenal"},
                "away_team": {"away_team_name": "Chelsea"},
            },
        ],
        (3, 500): [
            {
                "match_id": 201,
                "home_team": {"home_team_name": "Bayern Munich"},
                "away_team": {"away_team_name": "Arsenal"},
            }
        ],
    }

    monkeypatch.setattr(tools, "list_competitions", lambda **_: competitions)
    monkeypatch.setattr(
        tools,
        "list_matches",
        lambda competition_id, season_id, team_name=None, opponent_name=None, **_: [
            match
            for match in matches_lookup.get((competition_id, season_id), [])
            if (not team_name or team_name in {match["home_team"]["home_team_name"], match["away_team"]["away_team_name"]})
            and (
                not opponent_name
                or opponent_name
                in {
                    match["home_team"]["home_team_name"],
                    match["away_team"]["away_team_name"],
                }
            )
        ],
    )

    descriptors = find_matches_for_team(
        "Arsenal",
        season_name="2024/2025",
        opponent_name="Everton",
        use_cache=True,
    )

    assert [descriptor.match_id for descriptor in descriptors] == [101]


def test_fetch_player_season_stats_data_filters_and_sort(monkeypatch):
    rows = [
        {
            "player_name": "Bukayo Saka",
            "team_name": "Arsenal",
            "player_season_minutes": 900,
            "player_season_goals_90": 0.5,
        },
        {
            "player_name": "Martin Ødegaard",
            "team_name": "Arsenal",
            "player_season_minutes": 800,
            "player_season_goals_90": 0.2,
        },
    ]

    class DummyClient:
        def get_player_season_stats(self, *_, **__):
            return rows

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())

    result = tools.fetch_player_season_stats_data(
        2,
        317,
        team_name="Arsenal",
        player_names=["Bukayo Saka"],
        min_minutes=500,
        sort_by="player_season_goals_90",
        metrics=["player_name", "player_season_goals_90"],
    )

    assert len(result) == 1
    assert result[0]["player_name"] == "Bukayo Saka"


def test_fetch_team_season_stats_data_sort(monkeypatch):
    rows = [
        {"team_name": "Arsenal", "team_season_goals": 70},
        {"team_name": "Everton", "team_season_goals": 30},
    ]

    class DummyClient:
        def get_team_season_stats(self, *_, **__):
            return rows

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())

    result = tools.fetch_team_season_stats_data(
        2,
        317,
        sort_by="team_season_goals",
        top_n=1,
        metrics=["team_name"],
    )

    assert result == [{"team_name": "Arsenal"}]


def test_fetch_player_match_stats_data_filters(monkeypatch):
    rows = [
        {"player_name": "Bukayo Saka", "team_name": "Arsenal", "stat": 1},
        {"player_name": "Dominic Calvert-Lewin", "team_name": "Everton", "stat": 2},
    ]

    class DummyClient:
        def get_player_match_stats(self, *_, **__):
            return rows

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())

    result = tools.fetch_player_match_stats_data(
        3999,
        team_name="Arsenal",
        sort_by="stat",
    )

    assert result == [{"player_name": "Bukayo Saka", "team_name": "Arsenal", "stat": 1}]


def test_resolve_competition_id_alias():
    assert resolve_competition_id("Premier League") == 2
    assert resolve_competition_id("Bundesliga") == 9
    assert resolve_competition_id("Serie A") == 12
    assert resolve_competition_id("Ligue 1") == 7
    assert resolve_competition_id("Eredivisie") == 6
    assert resolve_competition_id("Jupiler Pro League") == 46
    assert resolve_competition_id("Primeira Liga") == 13
    assert resolve_competition_id("Major League Soccer") == 37
    assert resolve_competition_id("UEFA Champions League") == 16
    assert resolve_competition_id("UEFA Europa League") == 35
    assert resolve_competition_id("UEFA Europa Conference League") == 353
    assert resolve_competition_id("FA Cup") == 69
    assert resolve_competition_id("Copa del Rey") == 87
    assert resolve_competition_id("Coppa Italia") == 66
    assert resolve_competition_id("Coupe de France") == 86
    assert resolve_competition_id("DFB Pokal") == 165
    assert resolve_competition_id("Unknown League") is None


def test_season_id_for_label_uses_cache(monkeypatch):
    calls = []

    def fake_list_seasons(comp_id, **_):
        calls.append(comp_id)
        return [
            {"season_id": 317, "season_name": "2024/2025"},
            {"season_id": 318, "season_name": "2025/2026"},
        ]

    key = (2, tools._canonical("2024/2025"))
    original = tools._HARDCODED_SEASON_IDS.pop(key, None)

    monkeypatch.setattr(tools, "list_seasons", fake_list_seasons)
    sid = season_id_for_label(2, "2024/2025", use_cache=True)
    assert sid == 317
    # second call should hit cache
    sid2 = season_id_for_label(2, "2024/2025", use_cache=True)
    assert sid2 == 317
    assert calls.count(2) == 1

    if original is not None:
        tools._HARDCODED_SEASON_IDS[key] = original


def test_get_player_season_summary(monkeypatch):
    monkeypatch.setattr(
        tools,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    class DummyClient:
        def get_player_season_stats(self, *_, **__):
            return [
                {
                    "player_name": "Bukayo Saka",
                    "team_name": "Arsenal",
                    "player_season_minutes": 900,
                }
            ]

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())

    summary = get_player_season_summary(
        player_name="Bukayo Saka",
        season_label="2024/2025",
        competition_id=2,
    )

    assert summary["player_name"] == "Bukayo Saka"


def test_fetch_player_season_stats_data_handles_diacritics(monkeypatch):
    monkeypatch.setattr(
        tools,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    class DummyClient:
        def get_player_season_stats(self, *_, **__):
            return [
                {
                    "player_name": "Martin Ødegaard",
                    "team_name": "Arsenal",
                    "player_season_minutes": 1200,
                },
                {
                    "player_name": "Ángel Di María",
                    "team_name": "Benfica",
                    "player_season_minutes": 850,
                },
            ]

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())

    rows = tools.fetch_player_season_stats_data(
        2,
        317,
        player_names=["Martin Odegaard"],
        team_name="Arsenal",
    )

    assert [row["player_name"] for row in rows] == ["Martin Ødegaard"]

    rows_partial = tools.fetch_player_season_stats_data(
        2,
        317,
        player_names=["Odegaard"],
    )

    assert rows_partial and rows_partial[0]["player_name"] == "Martin Ødegaard"


def test_get_competition_players_returns_team_roster(monkeypatch):
    monkeypatch.setattr(
        tools,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    class DummyClient:
        def get_player_season_stats(self, *_, **__):
            return [
                {
                    "player_id": 1,
                    "player_name": "Bukayo Saka",
                    "team_name": "Arsenal",
                    "position": "FW",
                    "player_season_minutes": 900,
                    "player_season_goals": 10,
                },
                {
                    "player_id": 2,
                    "player_name": "Declan Rice",
                    "team_name": "Arsenal",
                    "position": "MF",
                    "player_season_minutes": 1100,
                    "player_season_goals": 5,
                },
            ]

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())

    rows = get_competition_players(
        competition_id=2,
        season_label="2024/2025",
        team_name="Arsenal",
        sort_by="player_season_goals",
        descending=True,
    )

    assert len(rows) == 2
    assert rows[0]["player_name"] == "Bukayo Saka"


def test_get_competition_players_preserves_identifiers_with_metrics(monkeypatch):
    monkeypatch.setattr(
        tools,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    class DummyClient:
        def get_player_season_stats(self, *_, **__):
            return [
                {
                    "player_id": 1,
                    "player_name": "Bukayo Saka",
                    "team_name": "Arsenal",
                    "position": "FW",
                    "player_season_minutes": 900,
                    "player_season_goals": 10,
                    "player_season_assists": 7,
                }
            ]

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())

    rows = get_competition_players(
        competition_id=2,
        season_label="2024/2025",
        metrics=["player_season_goals"],
    )

    assert rows[0]["player_name"] == "Bukayo Saka"
    assert rows[0]["team_name"] == "Arsenal"
    assert rows[0]["player_season_goals"] == 10


def test_get_team_season_summary(monkeypatch):
    monkeypatch.setattr(
        tools,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    class DummyClient:
        def get_team_season_stats(self, *_, **__):
            return [
                {"team_name": "Arsenal", "team_season_goals": 70},
                {"team_name": "Chelsea", "team_season_goals": 50},
            ]

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())

    summary = get_team_season_summary(
        team_name="Arsenal",
        season_label="2024/2025",
        competition_id=2,
    )

    assert summary["team_name"] == "Arsenal"


def test_get_player_multi_season_summary(monkeypatch):
    calls = []

    def fake_summary(**kwargs):
        calls.append(kwargs["season_label"])
        return {"player_name": "Bukayo Saka", "season_label": kwargs["season_label"]}

    monkeypatch.setattr(tools, "get_player_season_summary", fake_summary)

    summaries = get_player_multi_season_summary(
        player_name="Bukayo Saka",
        season_labels=["2023/2024", "2024/2025"],
        competition_id=2,
    )

    assert [s["season_label"] for s in summaries] == ["2023/2024", "2024/2025"]
    assert calls == ["2023/2024", "2024/2025"]


def test_get_players_season_summary(monkeypatch):
    rows = [
        {
            "player_name": "Bukayo Saka",
            "team_name": "Arsenal",
            "player_season_minutes": 900,
        },
        {
            "player_name": "Noni Madueke",
            "team_name": "Chelsea",
            "player_season_minutes": 750,
        },
        {
            "player_name": "Gabriel Jesus",
            "team_name": "Arsenal",
            "player_season_minutes": 800,
        },
    ]

    monkeypatch.setattr(
        tools,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    class DummyClient:
        def get_player_season_stats(self, *_, **__):
            return rows

    monkeypatch.setattr(tools, "get_statsbomb_client", lambda: DummyClient())

    summaries, missing = get_players_season_summary(
        player_names=["Saka", "Madueke"],
        season_label="2024/2025",
        competition_id=2,
    )

    assert list(summaries.keys()) == ["Saka", "Madueke"]
    assert missing == []


def test_count_player_passes_by_body_part(monkeypatch):
    match = _sample_match()
    descriptor1 = MatchDescriptor(match_id=1, competition_id=2, season_id=317)
    descriptor2 = MatchDescriptor(match_id=2, competition_id=2, season_id=317)

    event_left = {
        "type": {"name": "Pass"},
        "team": {"name": "Arsenal"},
        "player": {"name": "Bukayo Saka"},
        "pass": {"body_part": {"name": "Left Foot"}},
    }
    event_right = {
        "type": {"name": "Pass"},
        "team": {"name": "Arsenal"},
        "player": {"name": "Bukayo Saka"},
        "pass": {"body_part": {"name": "Right Foot"}},
    }
    context_left = EventContext(
        event=event_left,
        match=match,
        home_score=0,
        away_score=0,
        score_state="level",
        elapsed_seconds=60.0,
    )
    context_right = EventContext(
        event=event_right,
        match=match,
        home_score=0,
        away_score=0,
        score_state="level",
        elapsed_seconds=120.0,
    )

    dataset_map = {
        1: MatchDataset(descriptor1, match, [context_left]),
        2: MatchDataset(descriptor2, match, [context_right]),
    }

    monkeypatch.setattr(
        tools,
        "fetch_match_dataset",
        lambda descriptor, **_: dataset_map[descriptor.match_id],
    )

    summary = count_player_passes_by_body_part(
        [descriptor1, descriptor2],
        player_name="Bukayo Saka",
        body_part="Left Foot",
        team_name="Arsenal",
    )

    assert isinstance(summary, PlayerEventSummary)
    assert summary.total == 1
    assert summary.by_match[1] == 1
    assert summary.by_match[2] == 0
