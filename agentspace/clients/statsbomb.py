"""
StatsBomb API client implementation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..cache import DataCache
from ..config import APISettings
from ..http import HTTPClient


class StatsBombClient:
    """
    Provide typed wrappers around StatsBomb Data API endpoints.
    """

    def __init__(
        self,
        settings: Optional[APISettings] = None,
        *,
        cache: Optional[DataCache] = None,
    ):
        self.settings = settings or APISettings.from_env()
        self.http = HTTPClient(
            self.settings.statsbomb_base_url,
            auth_token=self.settings.statsbomb_token,
            username=self.settings.statsbomb_email,
            password=self.settings.statsbomb_password,
        )
        self.cache = cache or DataCache(self.settings.cache_dir)

    def _cache_suffix(self, data: Optional[Dict[str, Any]]) -> str:
        if not data:
            return "default"
        items = tuple(sorted(data.items()))
        return "_".join(f"{key}-{value}" for key, value in items)

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
        Fetch the list of competitions.
        """
        path = f"{self.settings.statsbomb_competitions_version}/competitions"
        return self._fetch(path, cache_key="competitions", use_cache=use_cache)

    def list_seasons(
        self, competition_id: int, *, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch seasons for a competition.
        """
        version = self.settings.statsbomb_seasons_version
        path = f"{version}/competitions/{competition_id}/seasons"
        cache_key = f"competition_{competition_id}_seasons"
        return self._fetch(path, cache_key=cache_key, use_cache=use_cache)

    def list_matches(
        self, competition_id: int, season_id: int, *, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch matches for a competition season.
        """
        path = (
            f"{self.settings.statsbomb_matches_version}/competitions/"
            f"{competition_id}/seasons/{season_id}/matches"
        )
        cache_key = f"matches_{competition_id}_{season_id}"
        return self._fetch(path, cache_key=cache_key, use_cache=use_cache)

    def get_events(
        self, match_id: int, *, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch event stream for a match.
        """
        path = f"{self.settings.statsbomb_events_version}/events/{match_id}"
        cache_key = f"events_{match_id}"
        return self._fetch(path, cache_key=cache_key, use_cache=use_cache)

    def get_360_frames(
        self, match_id: int, *, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch 360 freeze frames for a match.
        """
        path = f"{self.settings.statsbomb_360_version}/360-frames/{match_id}"
        cache_key = f"360_{match_id}"
        return self._fetch(path, cache_key=cache_key, use_cache=use_cache)

    def get_lineups(
        self, match_id: int, *, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch lineup information for a match.
        """
        path = f"{self.settings.statsbomb_lineups_version}/lineups/{match_id}"
        cache_key = f"lineups_{match_id}"
        return self._fetch(path, cache_key=cache_key, use_cache=use_cache)

    def get_team_season_stats(
        self,
        competition_id: int,
        season_id: int,
        *,
        use_cache: bool = True,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch aggregated season statistics for teams.
        """
        version = self.settings.statsbomb_team_stats_version
        path = (
            f"{version}/competitions/{competition_id}/seasons/{season_id}/team-stats"
        )
        cache_key = f"team_stats_{competition_id}_{season_id}_{self._cache_suffix(params)}"
        return self._fetch(path, params=params, cache_key=cache_key, use_cache=use_cache)

    def get_player_season_stats(
        self,
        competition_id: int,
        season_id: int,
        *,
        use_cache: bool = True,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch aggregated season statistics for players.
        """
        version = self.settings.statsbomb_player_stats_version
        path = (
            f"{version}/competitions/{competition_id}/seasons/{season_id}/player-stats"
        )
        cache_key = (
            f"player_stats_{competition_id}_{season_id}_{self._cache_suffix(params)}"
        )
        return self._fetch(path, params=params, cache_key=cache_key, use_cache=use_cache)

    def get_player_match_stats(
        self,
        match_id: int,
        *,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch player-level match statistics.
        """
        version = self.settings.statsbomb_player_match_stats_version
        path = f"{version}/matches/{match_id}/player-stats"
        cache_key = f"player_match_stats_{match_id}"
        return self._fetch(path, cache_key=cache_key, use_cache=use_cache)

    def get_team_match_stats(
        self,
        match_id: int,
        *,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch team-level match statistics.
        """
        version = self.settings.statsbomb_team_match_stats_version
        path = f"{version}/matches/{match_id}/team-stats"
        cache_key = f"team_match_stats_{match_id}"
        return self._fetch(path, cache_key=cache_key, use_cache=use_cache)
