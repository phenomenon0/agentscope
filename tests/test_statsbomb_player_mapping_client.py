from __future__ import annotations

from agentspace.clients.statsbomb import StatsBombClient
from agentspace.config import APISettings


def _settings(tmp_path) -> APISettings:
    return APISettings(
        statsbomb_base_url="https://statsbomb.test/api",
        statsbomb_token="token",
        statsbomb_email="user@example.com",
        statsbomb_password="secret",
        statsbomb_competitions_version="v4",
        statsbomb_matches_version="v6",
        statsbomb_events_version="v8",
        statsbomb_lineups_version="v4",
        statsbomb_360_version="v2",
        statsbomb_player_stats_version="v4",
        statsbomb_team_stats_version="v2",
        statsbomb_seasons_version="v6",
        statsbomb_player_match_stats_version="v5",
        statsbomb_team_match_stats_version="v1",
        wyscout_base_url="https://wyscout.test/api",
        wyscout_token="token",
        wyscout_client_id="client",
        wyscout_client_secret="secret",
        wyscout_api_version="v4",
        wyscout_aws_access_key="client",
        wyscout_aws_secret_key="secret",
        wyscout_aws_region="eu-west-1",
        wyscout_aws_service="execute-api",
        cache_dir=str(tmp_path),
        statsbomb_player_mapping_base_url="https://mapping.test/api",
        statsbomb_player_mapping_version="v1",
    )


def test_player_mapping_builds_expected_path(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    client = StatsBombClient(settings=settings)

    captured = {}

    def fake_request(self, method, path, *, params=None, json=None):  # noqa: ARG001, ANN001
        captured["method"] = method
        captured["path"] = path
        captured["params"] = params
        return []

    # patch the mapping client only
    monkeypatch.setattr(client, "http_mapping", type("X", (), {"request": fake_request})())

    client.get_player_mapping(
        competition_id=37,
        season_id=90,
        offline_player_id=10172,
        add_matches_played=True,
        all_account_data=False,
        use_cache=False,
    )

    assert captured["method"] == "GET"
    assert captured["path"] == "v1/player-mapping"
    # Ensure param names and value types
    assert captured["params"]["competition-id"] == 37
    assert captured["params"]["season-id"] == 90
    assert captured["params"]["offline-player-id"] == 10172
    assert captured["params"]["add-matches-played"] == "true"
