"""
Wyscout API client implementation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..cache import DataCache
from ..config import APISettings
from ..http import HTTPClient


class WyscoutClient:
    """
    Provide wrappers for Wyscout API endpoints.
    """

    def __init__(
        self,
        settings: Optional[APISettings] = None,
        *,
        cache: Optional[DataCache] = None,
    ):
        self.settings = settings or APISettings.from_env()
        self.http = HTTPClient(
            self.settings.wyscout_base_url,
            auth_token=self.settings.wyscout_token,
            username=self.settings.wyscout_client_id,
            password=self.settings.wyscout_client_secret,
        )
        self.cache = cache or DataCache(self.settings.cache_dir)

    def _fetch(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        cache_key: Optional[str] = None,
        use_cache: bool = True,
    ) -> Any:
        key = cache_key or path
        if use_cache:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        payload = self.http.request("GET", path, params=params)
        if use_cache and payload is not None:
            self.cache.set(key, payload)
        return payload

    def list_competitions(self, *, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch available competitions.
        """
        path = f"{self.settings.wyscout_api_version}/competitions"
        return self._fetch(path, cache_key="wyscout_competitions", use_cache=use_cache)

    def list_seasons(
        self, competition_id: int, *, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch seasons for a competition.
        """
        path = f"{self.settings.wyscout_api_version}/competitions/{competition_id}/seasons"
        cache_key = f"wyscout_competition_{competition_id}_seasons"
        return self._fetch(path, cache_key=cache_key, use_cache=use_cache)

    def list_matches(
        self, competition_id: int, season_id: int, *, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch matches for a competition season.
        """
        path = f"{self.settings.wyscout_api_version}/games/competition/{competition_id}/season/{season_id}"
        cache_key = f"wyscout_matches_{competition_id}_{season_id}"
        return self._fetch(path, cache_key=cache_key, use_cache=use_cache)

    def get_events(
        self, match_id: int, *, use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch detailed event data for a game.
        """
        path = f"{self.settings.wyscout_api_version}/events/{match_id}"
        cache_key = f"wyscout_events_{match_id}"
        return self._fetch(path, cache_key=cache_key, use_cache=use_cache)
