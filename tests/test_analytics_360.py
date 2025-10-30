import pytest

from agentspace.services import analytics360


@pytest.fixture(autouse=True)
def clear_cache():
    analytics360.clear_analytics360_cache()
    yield
    analytics360.clear_analytics360_cache()


def _match(team_id: int) -> dict:
    return {
        "match_id": 1,
        "home_team": {"home_team_id": team_id, "home_team_name": "Test FC"},
        "away_team": {"away_team_id": 999, "away_team_name": "Opposition"},
    }


def _pressure_event(team_id: int, event_id: str, location):
    return {
        "id": event_id,
        "event_uuid": event_id,
        "team": {"id": team_id},
        "type": {"name": "Pressure"},
        "location": location,
    }


def _touch_event(team_id: int, player_id: int, event_id: str, location):
    return {
        "id": event_id,
        "event_uuid": event_id,
        "team": {"id": team_id},
        "player": {"id": player_id},
        "type": {"name": "Touch"},
        "location": location,
    }


def test_team_metrics(monkeypatch):
    team_id = 42
    season_id = 100

    monkeypatch.setattr(analytics360, "season_id_for_label", lambda comp_id, label: season_id)
    monkeypatch.setattr(
        analytics360,
        "fetch_statsbomb_matches",
        lambda competition_id, season_id: [_match(team_id)],
    )

    events = [
        _pressure_event(team_id, "evt1", [60, 65]),
        _pressure_event(team_id, "evt2", [70, 20]),
    ]
    monkeypatch.setattr(
        analytics360,
        "fetch_statsbomb_events",
        lambda match_id: events,
    )
    frames = [
        {
            "event_uuid": "evt1",
            "players": [
                {"teammate": True, "keeper": False, "location": [40, 55]},
                {"teammate": True, "keeper": False, "location": [50, 57]},
            ],
        }
    ]
    monkeypatch.setattr(
        analytics360,
        "fetch_statsbomb_360",
        lambda match_id: frames,
    )

    result = analytics360.collect_team_360_metrics(
        competition_id=1,
        season_label="2024/2025",
        team_id=team_id,
        max_matches=1,
    )
    assert result["match_count"] == 1
    metric_map = {metric["key"]: metric for metric in result["metrics"]}
    assert metric_map["low_block_pressures"]["value"] == 1
    assert metric_map["avg_defensive_line"]["value"] == pytest.approx(56.0)


def test_player_metrics(monkeypatch):
    team_id = 42
    player_id = 9
    season_id = 200

    monkeypatch.setattr(analytics360, "season_id_for_label", lambda comp_id, label: season_id)

    monkeypatch.setattr(
        analytics360,
        "fetch_statsbomb_matches",
        lambda competition_id, season_id: [_match(team_id)],
    )

    events = [
        _touch_event(team_id, player_id, "touch1", [110, 40]),
        _touch_event(team_id, player_id, "touch2", [80, 30]),
    ]
    monkeypatch.setattr(
        analytics360,
        "fetch_statsbomb_events",
        lambda match_id: events,
    )
    frames = [
        {
            "event_uuid": "touch1",
            "players": [
                {"teammate": False, "nearest_defender": True, "distance": 1.8},
                {"teammate": False, "nearest_defender": True, "distance": 2.2},
            ],
        },
        {
            "event_uuid": "touch2",
            "players": [
                {"teammate": False, "nearest_defender": True, "distance": 3.0},
            ],
        },
    ]
    monkeypatch.setattr(
        analytics360,
        "fetch_statsbomb_360",
        lambda match_id: frames,
    )

    client_stub = type(
        "Client",
        (),
        {
            "get_player_season_stats": lambda self, comp_id, season_id, use_cache=True: [
                {"team_id": team_id, "player_id": player_id, "player_name": "Sample Player"}
            ]
        },
    )()
    monkeypatch.setattr(analytics360, "get_statsbomb_client", lambda: client_stub)

    result = analytics360.collect_player_360_metrics(
        competition_id=1,
        season_label="2024/2025",
        team_id=team_id,
        player_id=player_id,
        max_matches=1,
    )
    metric_map = {metric["key"]: metric for metric in result["metrics"]}
    assert metric_map["box_touches"]["value"] == 1
    assert metric_map["avg_defender_distance"]["value"] == pytest.approx(2.33, rel=1e-2)

