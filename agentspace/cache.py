"""
Simple disk backed cache for API responses.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional


class DataCache:
    """
    Persist JSON serialisable payloads on disk for reuse.
    """

    def __init__(self, cache_dir: str, default_ttl: Optional[int] = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl

    def _path_for_key(self, key: str) -> Path:
        safe_key = key.replace("/", "_")
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str, *, max_age: Optional[int] = None) -> Any:
        """
        Retrieve cached value if not expired.
        """
        path = self._path_for_key(key)
        if not path.exists():
            return None

        ttl = max_age if max_age is not None else self.default_ttl
        if ttl is not None:
            mtime = path.stat().st_mtime
            if (time.time() - mtime) > ttl:
                return None

        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: Any) -> None:
        """
        Store value in the cache.
        """
        path = self._path_for_key(key)
        tmp_path = Path(f"{path}.{os.getpid()}.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(value, handle)
        tmp_path.replace(path)

    def clear(self) -> None:
        """
        Remove all cached entries.
        """
        for file in self.cache_dir.glob("*.json"):
            file.unlink()
