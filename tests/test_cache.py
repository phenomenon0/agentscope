from __future__ import annotations

import json
import time

from agentspace.cache import DataCache


def test_cache_roundtrip(tmp_path):
    cache = DataCache(str(tmp_path))
    cache.set("key", {"a": 1})
    loaded = cache.get("key")
    assert loaded == {"a": 1}


def test_cache_respects_ttl(tmp_path):
    cache = DataCache(str(tmp_path), default_ttl=1)
    cache.set("key", {"a": 1})
    assert cache.get("key") == {"a": 1}
    time.sleep(1.2)
    assert cache.get("key") is None
