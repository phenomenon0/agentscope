from __future__ import annotations

from agentscope.tool import Toolkit

from agentspace.agent_tools import wyscout as wyscout_tools
from agentspace.services import data_fetch


class DummyClient:
    def __init__(
        self,
        *,
        areas=None,
        competitions=None,
        seasons=None,
        matches=None,
        competition_players=None,
        events=None,
        match_events=None,
        player_adv_stats=None,
        match_adv_stats=None,
        match_player_adv_stats=None,
    ):
        self._areas = areas or []
        self._competitions = competitions or []
        self._seasons = seasons or []
        self._matches = matches or []
        self._competition_players = competition_players or []
        self._events = events or {}
        self._match_events = match_events or {}
        self._player_adv_stats = player_adv_stats or {"summary": {"value": 1}}
        self._match_adv_stats = match_adv_stats or {"metrics": []}
        self._match_player_adv_stats = match_player_adv_stats or {"players": []}
        self._list_areas_calls = 0

    def list_areas(self, use_cache=True):  # noqa: ARG002
        self._list_areas_calls += 1
        return self._areas

    def list_competitions(self, area_id=None, use_cache=True):  # noqa: ARG002
        self._last_area_id = area_id
        return self._competitions

    def list_seasons(self, competition_id, use_cache=True):  # noqa: ARG002
        return self._seasons

    def list_matches(self, competition_id, season_id, use_cache=True):  # noqa: ARG002
        return self._matches

    def list_competition_players(self, competition_id, params=None, use_cache=True):  # noqa: ARG002
        self._last_player_params = params
        return self._competition_players

    def get_events(self, match_id, use_cache=True):  # noqa: ARG002
        return self._events

    def get_match_events(self, match_id, params=None, use_cache=True):  # noqa: ARG002
        self._last_match_event_params = params
        return self._match_events

    def get_player_advanced_stats(self, player_id, params=None, use_cache=True):  # noqa: ARG002
        self._last_player_adv_params = params
        self._last_player_adv_id = player_id
        return self._player_adv_stats

    def get_match_advanced_stats(self, match_id, params=None, use_cache=True):  # noqa: ARG002
        self._last_match_adv_params = params
        self._last_match_adv_id = match_id
        return self._match_adv_stats

    def get_match_players_advanced_stats(self, match_id, params=None, use_cache=True):  # noqa: ARG002
        self._last_match_players_adv_params = params
        self._last_match_players_adv_id = match_id
        return self._match_player_adv_stats


def test_register_wyscout_tools():
    toolkit = wyscout_tools.register_wyscout_tools(Toolkit(), group_name="wyscout", activate=True)
    names = [schema["function"]["name"] for schema in toolkit.get_json_schemas()]
    for expected in (
        "list_wyscout_areas",
        "list_wyscout_competitions",
        "list_wyscout_seasons",
        "list_wyscout_matches",
        "list_wyscout_competition_players",
        "get_wyscout_player_advanced_stats",
        "get_wyscout_match_advanced_stats",
        "get_wyscout_match_player_advanced_stats",
        "get_wyscout_events",
    ):
        assert expected in names


def test_list_wyscout_areas(monkeypatch):
    monkeypatch.setattr(
        data_fetch,
        "get_wyscout_common_areas",
        lambda: [
            {"id": 1100, "name": "Test Area", "alpha2code": "TA", "aliases": ["test"]},
        ],
    )
    client = DummyClient(
        areas=[
            {"id": 1100, "name": "Test Area", "alpha2code": "TA"},
        ]
    )
    monkeypatch.setattr(wyscout_tools, "_client", lambda: client)

    response = wyscout_tools.list_wyscout_areas(use_cache=False)
    assert response.metadata["areas"][0]["id"] == 1100
    assert "Test Area" in response.content[0]["text"]
    assert response.metadata["source"] == "common"
    assert client._list_areas_calls == 0


def test_list_wyscout_areas_live(monkeypatch):
    monkeypatch.setattr(
        data_fetch,
        "get_wyscout_common_areas",
        lambda: [],
    )
    client = DummyClient(
        areas=[
            {"id": 2000, "name": "Live Area", "alpha2code": "LA"},
        ]
    )
    monkeypatch.setattr(wyscout_tools, "_client", lambda: client)

    response = wyscout_tools.list_wyscout_areas(source="live", use_cache=False)
    assert response.metadata["areas"][0]["name"] == "Live Area"
    assert response.metadata["source"] == "live"
    assert client._list_areas_calls == 1


def test_list_wyscout_competitions(monkeypatch):
    client = DummyClient(
        competitions=[
            {"competitionId": 99, "name": "Liga Test", "category": "League"},
        ]
    )
    monkeypatch.setattr(wyscout_tools, "_client", lambda: client)
    monkeypatch.setattr(
        data_fetch,
        "resolve_wyscout_area",
        lambda identifier, use_cache=True: {"id": 1100, "name": "Test Area"}
        if identifier in (1100, "Test Area")
        else None,
    )

    response = wyscout_tools.list_wyscout_competitions(area_id="Test Area", use_cache=False)
    assert response.metadata["competitions"][0]["competitionId"] == 99
    assert response.metadata["filters"]["resolved_area_id"] == 1100
    assert response.metadata["filters"]["resolved_area"]["name"] == "Test Area"
    assert response.metadata["known_competition_ids"]["England"]["Premier League"] == 364
    assert "Liga Test" in response.content[0]["text"]
    assert client._last_area_id == 1100


def test_list_wyscout_competitions_unresolved(monkeypatch):
    client = DummyClient()
    monkeypatch.setattr(wyscout_tools, "_client", lambda: client)
    monkeypatch.setattr(
        data_fetch,
        "resolve_wyscout_area",
        lambda identifier, use_cache=True: None,
    )

    response = wyscout_tools.list_wyscout_competitions(area_id="Unknown", use_cache=False)
    assert not response.metadata["competitions"]
    assert response.metadata["filters"]["resolved_area"] is None
    assert "Unable to resolve" in response.content[0]["text"]


def test_list_wyscout_matches_filters(monkeypatch):
    matches = [
        {
            "matchId": 1,
            "teams": {
                "home": {"name": "Team Alpha"},
                "away": {"name": "Team Beta"},
            },
            "date": "2024-08-01",
        },
        {
            "matchId": 2,
            "teams": {
                "home": {"name": "Team Gamma"},
                "away": {"name": "Team Delta"},
            },
            "date": "2024-08-02",
        },
    ]
    client = DummyClient(matches=matches)
    monkeypatch.setattr(wyscout_tools, "_client", lambda: client)

    response = wyscout_tools.list_wyscout_matches(10, 20, team_name="Alpha")
    data = response.metadata["matches"]
    assert len(data) == 1
    assert data[0]["matchId"] == 1
    assert "Team Alpha" in response.content[0]["text"]


def test_list_wyscout_competition_players(monkeypatch):
    players = [
        {"wyId": 101, "shortName": "Player One", "role": {"name": "Defender"}},
        {"wyId": 102, "shortName": "Player Two", "role": {"name": "Midfielder"}},
    ]
    client = DummyClient(competition_players=players)
    monkeypatch.setattr(wyscout_tools, "_client", lambda: client)

    response = wyscout_tools.list_wyscout_competition_players(364, season_id=2025, limit=100)
    assert len(response.metadata["players"]) == 2
    assert response.metadata["params"]["seasonId"] == 2025
    assert "Player One" in response.content[0]["text"]
    assert client._last_player_params["limit"] == 100


def test_get_wyscout_player_advanced_stats(monkeypatch):
    client = DummyClient(player_adv_stats={"summary": {"xg": 0.4}})
    monkeypatch.setattr(wyscout_tools, "_client", lambda: client)

    response = wyscout_tools.get_wyscout_player_advanced_stats(
        21809,
        competition_id=364,
        season_id=2025,
    )
    assert response.metadata["player_id"] == 21809
    assert response.metadata["stats"]["summary"]["xg"] == 0.4
    assert client._last_player_adv_params["competitionId"] == 364


def test_get_wyscout_match_advanced_stats(monkeypatch):
    client = DummyClient(match_adv_stats={"metrics": [{"name": "xG", "value": 1.2}]})
    monkeypatch.setattr(wyscout_tools, "_client", lambda: client)

    response = wyscout_tools.get_wyscout_match_advanced_stats(
        555,
        competition_id=364,
        season_id=2025,
        round_id=12,
    )
    assert response.metadata["match_id"] == 555
    assert response.metadata["stats"]["metrics"][0]["name"] == "xG"
    assert client._last_match_adv_params["roundId"] == 12


def test_get_wyscout_match_player_advanced_stats(monkeypatch):
    client = DummyClient(match_player_adv_stats={"players": [{"wyId": 1}, {"wyId": 2}]})
    monkeypatch.setattr(wyscout_tools, "_client", lambda: client)

    response = wyscout_tools.get_wyscout_match_player_advanced_stats(
        555,
        competition_id=364,
        season_id=2025,
    )
    assert response.metadata["match_id"] == 555
    assert response.metadata["stats"]["players"][0]["wyId"] == 1
    assert client._last_match_players_adv_params["detail"] == "player"


def test_get_wyscout_events(monkeypatch):
    client = DummyClient(
        match_events={"events": [{"id": 1}, {"id": 2}]},
        events={"events": []},
    )
    monkeypatch.setattr(wyscout_tools, "_client", lambda: client)

    response = wyscout_tools.get_wyscout_events(555, include_player_details=True)
    assert response.metadata["match_id"] == 555
    assert response.metadata["events"]["events"][0]["id"] == 1
    assert "Event count" in response.content[0]["text"]
    assert client._last_match_event_params["detail"] == "player"
