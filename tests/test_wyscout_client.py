from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from requests import Response

from agentspace.cache import DataCache
from agentspace.clients.wyscout import WyscoutClient
from agentspace.config import APISettings
from agentspace.exceptions import APINotFoundError


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
        wyscout_api_version="v1",
        cache_dir=str(tmp_path),
    )


def _response(status_code: int, payload: Any, url: str) -> Response:
    response = Response()
    response.status_code = status_code
    response._content = json.dumps(payload).encode("utf-8")
    response.headers["Content-Type"] = "application/json"
    response.url = url
    return response


def test_wyscout_list_matches_builds_expected_path(tmp_path):
    settings = _settings(tmp_path)
    client = WyscoutClient(settings=settings, cache=DataCache(settings.cache_dir))
    payload = [{"matchId": 1}]

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(
            200, payload, url="https://wyscout.test/api/v1/games/competition/9/season/42"
        )
        matches = client.list_matches(9, 42, use_cache=False)

    assert matches == payload
    args, kwargs = mock_request.call_args
    assert kwargs["url"].endswith("/v1/games/competition/9/season/42")


def test_wyscout_cache_hit_avoids_http(tmp_path):
    settings = _settings(tmp_path)
    cache = DataCache(settings.cache_dir)
    client = WyscoutClient(settings=settings, cache=cache)
    payload = [{"competitionId": 9}]

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(200, payload, url="https://wyscout.test/api/v1/competitions")
        first = client.list_competitions()
        assert first == payload
        assert mock_request.call_count == 1

        second = client.list_competitions()
        assert second == payload
        assert mock_request.call_count == 1


def test_wyscout_get_events_hits_expected_endpoint(tmp_path):
    settings = _settings(tmp_path)
    client = WyscoutClient(settings=settings, cache=DataCache(settings.cache_dir))
    payload = {"events": []}

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(200, payload, url="https://wyscout.test/api/v1/events/777")
        events = client.get_events(777, use_cache=False)

    assert events == payload
    args, kwargs = mock_request.call_args
    assert kwargs["url"].endswith("/v1/events/777")


def test_wyscout_404_raises_not_found(tmp_path):
    settings = _settings(tmp_path)
    client = WyscoutClient(settings=settings, cache=DataCache(settings.cache_dir))

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(404, {}, url="https://wyscout.test/api/v1/events/999")
        with pytest.raises(APINotFoundError):
            client.get_events(999, use_cache=False)
