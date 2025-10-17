from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from requests import Response

from agentspace.cache import DataCache
from agentspace.clients.statsbomb import StatsBombClient
from agentspace.config import APISettings
from agentspace.exceptions import APIClientError, APINotFoundError, APIRateLimitError


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


def _response(status_code: int, payload: Any, url: str = "https://statsbomb.test/api") -> Response:
    response = Response()
    response.status_code = status_code
    response._content = json.dumps(payload).encode("utf-8")
    response.headers["Content-Type"] = "application/json"
    response.url = url
    return response


def test_list_competitions_uses_cache(tmp_path):
    settings = _settings(tmp_path)
    cache = DataCache(settings.cache_dir)
    client = StatsBombClient(settings=settings, cache=cache)

    payload = [{"competition_id": 1, "competition_name": "Test League"}]

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(200, payload, url="https://statsbomb.test/api/v4/competitions")

        first = client.list_competitions()
        assert first == payload
        assert mock_request.call_count == 1

        second = client.list_competitions()
        assert second == payload
        assert mock_request.call_count == 1  # No extra HTTP call thanks to cache


def test_player_season_stats_hits_expected_endpoint(tmp_path):
    settings = _settings(tmp_path)
    cache = DataCache(settings.cache_dir)
    client = StatsBombClient(settings=settings, cache=cache)

    payload = [{"player_id": 10}]

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(
            200,
            payload,
            url="https://statsbomb.test/api/v4/competitions/9/seasons/42/player-stats",
        )
        result = client.get_player_season_stats(9, 42, use_cache=False)

    assert result == payload
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert kwargs["url"].endswith("/v4/competitions/9/seasons/42/player-stats")
    assert kwargs["params"] is None


def test_get_360_uses_expected_path(tmp_path):
    settings = _settings(tmp_path)
    cache = DataCache(settings.cache_dir)
    client = StatsBombClient(settings=settings, cache=cache)
    payload = [{"freeze_frame": []}]

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(200, payload, url="https://statsbomb.test/api/v2/360-frames/1234")
        frames = client.get_360_frames(1234, use_cache=False)

    assert frames == payload
    _, kwargs = mock_request.call_args
    assert kwargs["method"] == "GET"
    assert kwargs["url"].endswith("/v2/360-frames/1234")


def test_get_lineups_hits_expected_path(tmp_path):
    settings = _settings(tmp_path)
    cache = DataCache(settings.cache_dir)
    client = StatsBombClient(settings=settings, cache=cache)
    payload = [{"lineup": []}]

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(200, payload, url="https://statsbomb.test/api/v4/lineups/1234")
        lineups = client.get_lineups(1234, use_cache=False)

    assert lineups == payload
    _, kwargs = mock_request.call_args
    assert kwargs["url"].endswith("/v4/lineups/1234")


def test_get_player_match_stats_hits_expected_endpoint(tmp_path):
    settings = _settings(tmp_path)
    cache = DataCache(settings.cache_dir)
    client = StatsBombClient(settings=settings, cache=cache)
    payload = [{"player_id": 10}]

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(
            200,
            payload,
            url="https://statsbomb.test/api/v5/matches/123/player-stats",
        )
        stats = client.get_player_match_stats(123, use_cache=False)

    assert stats == payload
    _, kwargs = mock_request.call_args
    assert kwargs["url"].endswith("/v5/matches/123/player-stats")


def test_get_team_match_stats_hits_expected_endpoint(tmp_path):
    settings = _settings(tmp_path)
    cache = DataCache(settings.cache_dir)
    client = StatsBombClient(settings=settings, cache=cache)
    payload = [{"team_id": 1}]

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(
            200,
            payload,
            url="https://statsbomb.test/api/v1/matches/123/team-stats",
        )
        stats = client.get_team_match_stats(123, use_cache=False)

    assert stats == payload
    _, kwargs = mock_request.call_args
    assert kwargs["url"].endswith("/v1/matches/123/team-stats")


def test_list_seasons_hits_expected_endpoint(tmp_path):
    settings = _settings(tmp_path)
    client = StatsBombClient(settings=settings, cache=DataCache(settings.cache_dir))
    payload = [{"season_id": 1}]

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(
            200, payload, url="https://statsbomb.test/api/v6/competitions/9/seasons"
        )
        seasons = client.list_seasons(9, use_cache=False)

    assert seasons == payload
    args, kwargs = mock_request.call_args
    assert kwargs["url"].endswith("/v6/competitions/9/seasons")


def test_team_season_stats_hits_expected_endpoint(tmp_path):
    settings = _settings(tmp_path)
    cache = DataCache(settings.cache_dir)
    client = StatsBombClient(settings=settings, cache=cache)
    payload = [{"team_id": 1}]

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(
            200,
            payload,
            url="https://statsbomb.test/api/v2/competitions/9/seasons/42/team-stats",
        )
        result = client.get_team_season_stats(9, 42, use_cache=False)

    assert result == payload
    mock_request.assert_called_once()
    _, kwargs = mock_request.call_args
    assert kwargs["url"].endswith("/v2/competitions/9/seasons/42/team-stats")
    assert kwargs["params"] is None


def test_list_matches_hits_expected_endpoint(tmp_path):
    settings = _settings(tmp_path)
    client = StatsBombClient(settings=settings, cache=DataCache(settings.cache_dir))
    payload = [{"match_id": 500}]

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(
            200,
            payload,
            url="https://statsbomb.test/api/v6/competitions/9/seasons/99/matches",
        )
        matches = client.list_matches(9, 99, use_cache=False)

    assert matches == payload
    args, kwargs = mock_request.call_args
    assert kwargs["url"].endswith("/v6/competitions/9/seasons/99/matches")


def test_http_errors_are_mapped(tmp_path):
    settings = _settings(tmp_path)
    client = StatsBombClient(settings=settings, cache=DataCache(settings.cache_dir))

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(404, {}, url="https://statsbomb.test/api/v8/events/123")
        with pytest.raises(APINotFoundError):
            client.get_events(123, use_cache=False)

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = _response(429, {}, url="https://statsbomb.test/api/v8/events/124")
        with pytest.raises(APIRateLimitError):
            client.get_events(124, use_cache=False)


def test_non_json_response_raises_client_error(tmp_path):
    settings = _settings(tmp_path)
    client = StatsBombClient(settings=settings, cache=DataCache(settings.cache_dir))

    response = Response()
    response.status_code = 200
    response._content = b"<html>not json</html>"
    response.headers["Content-Type"] = "text/html"

    with patch.object(client.http.session, "request") as mock_request:
        mock_request.return_value = response
        with pytest.raises(APIClientError):
            client.list_competitions(use_cache=False)
