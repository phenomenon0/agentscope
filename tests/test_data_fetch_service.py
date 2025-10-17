from __future__ import annotations

import types
from agentspace.services import data_fetch


def test_get_match_ids_statsbomb_branch(monkeypatch):
    fake_matches = [{"match_id": 1}, {"match_id": 2}]

    def fake_fetch(comp, season):
        assert comp == 10
        assert season == 99
        return fake_matches

    monkeypatch.setattr(data_fetch, "fetch_statsbomb_matches", fake_fetch)
    ids = data_fetch.get_match_ids([10], 99, source="statsbomb")
    assert ids == [1, 2]


def test_get_match_ids_wyscout_branch(monkeypatch):
    fake_matches = [{"matchId": 3}, {"matchId": 4}]

    def fake_fetch(comp, season):
        assert comp == 10
        assert season == 99
        return fake_matches

    monkeypatch.setattr(data_fetch, "fetch_wyscout_matches", fake_fetch)
    ids = data_fetch.get_match_ids([10], 99, source="wyscout")
    assert ids == [3, 4]


def test_get_match_ids_raises_for_unknown_source():
    try:
        data_fetch.get_match_ids([1], 1, source="unknown")
        raise AssertionError("Expected error")
    except Exception as exc:
        assert "Unsupported data source" in str(exc)


def test_fetch_statsbomb_events_delegates(monkeypatch):
    called = {}

    class FakeClient:
        def get_events(self, match_id, use_cache=True):
            called["match_id"] = match_id
            called["use_cache"] = use_cache
            return [{"id": 1}]

    monkeypatch.setattr(data_fetch, "_statsbomb_client", lambda: FakeClient())

    events = data_fetch.fetch_statsbomb_events(55)
    assert events == [{"id": 1}]
    assert called["match_id"] == 55


def test_fetch_wyscout_events_delegates(monkeypatch):
    called = {}

    class FakeClient:
        def get_events(self, match_id, use_cache=True):
            called["match_id"] = match_id
            return {"events": []}

    monkeypatch.setattr(data_fetch, "_wyscout_client", lambda: FakeClient())

    events = data_fetch.fetch_wyscout_events(77)
    assert events == {"events": []}
    assert called["match_id"] == 77
