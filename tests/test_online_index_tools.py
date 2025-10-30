from __future__ import annotations

from agentscope.tool import Toolkit
from agentspace.agent_tools.online_index import (
    register_statsbomb_online_index_tools,
    find_player_online,
    find_team_players_online,
    get_player_matches_online,
    list_seasons_online,
)


class DummyClient:
    def __init__(self, rows):
        self.rows = rows

    def get_player_mapping(self, **kwargs):  # noqa: ANN001
        # Filter by competition/season if provided
        cid = kwargs.get("competition_id")
        sid = kwargs.get("season_id")
        res = self.rows
        if cid is not None:
            res = [r for r in res if r.get("competition_id") == cid]
        if sid is not None:
            res = [r for r in res if r.get("season_id") == sid]
        return res


ROWS = [
    {
        "competition_id": 37,
        "season_id": 90,
        "season_name": "2020/2021",
        "offline_team_id": 746,
        "team_name": "Manchester City WFC",
        "offline_player_id": 10172,
        "player_name": "Jill Scott",
        "most_recent_match_date": "2021-01-17",
        "matches_played": [
            {"offline_match_id": 3764234, "match_date": "2020-09-05"},
            {"offline_match_id": 3775611, "match_date": "2021-01-17"},
        ],
    },
    {
        "competition_id": 37,
        "season_id": 90,
        "season_name": "2020/2021",
        "offline_team_id": 967,
        "team_name": "Everton LFC",
        "offline_player_id": 10172,
        "player_name": "Jill Scott",
        "most_recent_match_date": "2021-05-09",
        "matches_played": [
            {"offline_match_id": 3775563, "match_date": "2021-05-09"}
        ],
    },
    {
        "competition_id": 37,
        "season_id": 91,
        "season_name": "2021/2022",
        "offline_team_id": 217,
        "team_name": "Barcelona",
        "offline_player_id": 5503,
        "player_name": "Lionel Messi",
        "most_recent_match_date": "2022-05-01",
        "matches_played": [],
    },
]


def test_online_index_tools_register():
    tk = register_statsbomb_online_index_tools(Toolkit(), activate=True)
    schemas = tk.get_json_schemas()
    names = [s["function"]["name"] for s in schemas]
    assert "find_player_online" in names
    assert "find_team_players_online" in names
    assert "get_player_matches_online" in names
    assert "list_seasons_online" in names


def test_find_player_online(monkeypatch):
    from agentspace.agent_tools import online_index as online

    client = DummyClient(ROWS)
    monkeypatch.setattr(online, "StatsBombClient", lambda: client)

    res = find_player_online("Jill Scott", competition_id=37, season_id=90)
    assert res.metadata
    players = res.metadata["players"]
    assert players and players[0]["offline_player_id"] == 10172


def test_find_team_players_online(monkeypatch):
    from agentspace.agent_tools import online_index as online

    client = DummyClient(ROWS)
    monkeypatch.setattr(online, "StatsBombClient", lambda: client)

    res = find_team_players_online("Everton", competition_id=37, season_id=90)
    assert res.metadata
    players = res.metadata["players"]
    assert any(p["player_name"] == "Jill Scott" for p in players)


def test_get_player_matches_online(monkeypatch):
    from agentspace.agent_tools import online_index as online

    client = DummyClient(ROWS)
    monkeypatch.setattr(online, "StatsBombClient", lambda: client)

    res = get_player_matches_online(offline_player_id=10172, competition_id=37, season_id=90)
    assert res.metadata
    matches = res.metadata["matches"]
    ids = {m["offline_match_id"] for m in matches}
    assert 3775611 in ids and 3764234 in ids


def test_list_seasons_online(monkeypatch):
    from agentspace.agent_tools import online_index as online

    client = DummyClient(ROWS)
    monkeypatch.setattr(online, "StatsBombClient", lambda: client)

    res = list_seasons_online(competition_id=37)
    seasons = res.metadata["seasons"]
    sids = {s["season_id"] for s in seasons}
    assert 90 in sids and 91 in sids

