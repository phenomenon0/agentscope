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
        wyscout_api_version="v4",
        wyscout_aws_access_key="client",
        wyscout_aws_secret_key="secret",
        wyscout_aws_region="eu-west-1",
        wyscout_aws_service="execute-api",
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
    payload = {"matches": [{"matchId": 1}]}

    with patch.object(client.http.session, "request") as mock_request:
        version = settings.wyscout_api_version
        mock_request.return_value = _response(
            200, payload, url=f"https://wyscout.test/api/{version}/games/competition/9/season/42"
        )
        matches = client.list_matches(9, 42, use_cache=False)

    assert matches == payload["matches"]
    args, kwargs = mock_request.call_args
    assert kwargs["url"].endswith(f"/{version}/games/competition/9/season/42")


def test_wyscout_cache_hit_avoids_http(tmp_path):
    settings = _settings(tmp_path)
    cache = DataCache(settings.cache_dir)
    client = WyscoutClient(settings=settings, cache=cache)
    payload = {"competitions": [{"competitionId": 9}]}

    with patch.object(client.http.session, "request") as mock_request:
        version = settings.wyscout_api_version
        mock_request.return_value = _response(
            200,
            payload,
            url=f"https://wyscout.test/api/{version}/competitions?areaId=1100",
        )
        first = client.list_competitions(area_id=1100)
        assert first == payload["competitions"]
        assert mock_request.call_count == 1
        _, kwargs = mock_request.call_args
        assert kwargs["params"] == {"areaId": 1100}

        second = client.list_competitions(area_id=1100)
        assert second == payload["competitions"]
        assert mock_request.call_count == 1


def test_wyscout_list_areas_hits_expected_endpoint(tmp_path):
    settings = _settings(tmp_path)
    client = WyscoutClient(settings=settings, cache=DataCache(settings.cache_dir))
    payload = {"areas": [{"id": 1100}]}

    with patch.object(client.http.session, "request") as mock_request:
        version = settings.wyscout_api_version
        mock_request.return_value = _response(
            200, payload, url=f"https://wyscout.test/api/{version}/areas"
        )
        areas = client.list_areas(use_cache=False)

    assert areas == payload["areas"]
    args, kwargs = mock_request.call_args
    assert kwargs["url"].endswith(f"/{version}/areas")


def test_wyscout_get_events_hits_expected_endpoint(tmp_path):
    settings = _settings(tmp_path)
    client = WyscoutClient(settings=settings, cache=DataCache(settings.cache_dir))
    payload = {"events": []}

    with patch.object(client.http.session, "request") as mock_request:
        version = settings.wyscout_api_version
        mock_request.return_value = _response(
            200, payload, url=f"https://wyscout.test/api/{version}/events/777"
        )
        events = client.get_events(777, use_cache=False)

    assert events == payload
    args, kwargs = mock_request.call_args
    assert kwargs["url"].endswith(f"/{version}/events/777")


def test_wyscout_404_raises_not_found(tmp_path):
    settings = _settings(tmp_path)
    client = WyscoutClient(settings=settings, cache=DataCache(settings.cache_dir))

    with patch.object(client.http.session, "request") as mock_request:
        version = settings.wyscout_api_version
        mock_request.return_value = _response(
            404, {}, url=f"https://wyscout.test/api/{version}/events/999"
        )
        with pytest.raises(APINotFoundError):
            client.get_events(999, use_cache=False)


def test_common_area_index_contains_europe():
    index = WyscoutClient.common_area_index()
    assert any(area["id"] == 1106 and area["name"] == "Europe" for area in index)


def test_resolve_area_uses_common_index(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    client = WyscoutClient(settings=settings, cache=DataCache(settings.cache_dir))

    def fail_list_areas(use_cache=True):  # noqa: ARG001
        raise AssertionError("list_areas should not be called for common entries")

    monkeypatch.setattr(client, "list_areas", fail_list_areas)

    resolved = client.resolve_area("Europe")
    assert resolved["id"] == 1106


def test_resolve_area_falls_back_to_live(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    client = WyscoutClient(settings=settings, cache=DataCache(settings.cache_dir))

    monkeypatch.setattr(
        client,
        "list_areas",
        lambda use_cache=True: [
            {"id": 9999, "name": "Testland", "alpha2code": "TL"},
        ],
    )

    resolved = client.resolve_area("Testland")
    assert resolved["id"] == 9999
