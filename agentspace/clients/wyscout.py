"""
Wyscout API client implementation.
"""
from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional, Union

from ..cache import DataCache
from ..config import APISettings
from ..http import HTTPClient


def _normalize_area_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _clone_area_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(entry)
    if "aliases" in data:
        data["aliases"] = list(entry["aliases"])
    return data


_COMMON_AREAS: List[Dict[str, Any]] = [
    {
        "id": 1420,
        "name": "World",
        "alpha2code": "WO",
        "alpha3code": "XWO",
        "aliases": ("world", "global", "international"),
    },
    {
        "id": 1106,
        "name": "Europe",
        "alpha2code": "EU",
        "alpha3code": "XEU",
        "aliases": ("europe", "uefa"),
    },
    {
        "id": 1104,
        "name": "South America",
        "alpha2code": "SA",
        "alpha3code": "XSA",
        "aliases": ("southamerica", "conmebol"),
    },
    {
        "id": 1103,
        "name": "N/C America",
        "alpha2code": "NC",
        "alpha3code": "XNC",
        "aliases": ("northamerica", "concacaf", "centralamerica"),
    },
    {
        "id": 1101,
        "name": "Asia",
        "alpha2code": "AS",
        "alpha3code": "XAS",
        "aliases": ("asia", "afc"),
    },
    {
        "id": 1102,
        "name": "Africa",
        "alpha2code": "AF",
        "alpha3code": "XAF",
        "aliases": ("africa", "caf"),
    },
    {
        "id": 1105,
        "name": "Oceania",
        "alpha2code": "OC",
        "alpha3code": "XOC",
        "aliases": ("oceania", "ofc"),
    },
    {
        "id": 826,
        "name": "England",
        "alpha2code": "EN",
        "alpha3code": "XEN",
        "aliases": ("england", "eng"),
    },
    {
        "id": 724,
        "name": "Spain",
        "alpha2code": "ES",
        "alpha3code": "ESP",
        "aliases": ("spain", "esp"),
    },
    {
        "id": 380,
        "name": "Italy",
        "alpha2code": "IT",
        "alpha3code": "ITA",
        "aliases": ("italy", "ita"),
    },
    {
        "id": 276,
        "name": "Germany",
        "alpha2code": "DE",
        "alpha3code": "DEU",
        "aliases": ("germany", "ger"),
    },
    {
        "id": 250,
        "name": "France",
        "alpha2code": "FR",
        "alpha3code": "FRA",
        "aliases": ("france", "fra"),
    },
    {
        "id": 32,
        "name": "Argentina",
        "alpha2code": "AR",
        "alpha3code": "ARG",
        "aliases": ("argentina", "arg"),
    },
    {
        "id": 76,
        "name": "Brazil",
        "alpha2code": "BR",
        "alpha3code": "BRA",
        "aliases": ("brazil", "bra"),
    },
    {
        "id": 840,
        "name": "United States",
        "alpha2code": "US",
        "alpha3code": "USA",
        "aliases": ("unitedstates", "usa", "united states"),
    },
]

_COMMON_AREA_LOOKUP: Dict[str, Dict[str, Any]] = {}
for _area in _COMMON_AREAS:
    tokens = set(_area.get("aliases", ()))
    tokens.add(_area["name"])
    for key in ("alpha2code", "alpha3code"):
        code = _area.get(key)
        if code:
            tokens.add(code)
    for token in tokens:
        if not token:
            continue
        norm = _normalize_area_key(str(token))
        if norm and norm not in _COMMON_AREA_LOOKUP:
            _COMMON_AREA_LOOKUP[norm] = _area


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
        auth_token = self.settings.wyscout_token
        self.http = HTTPClient(
            self.settings.wyscout_base_url,
            auth_token=auth_token,
        )

        basic_header = None
        if not auth_token:
            client_id = self.settings.wyscout_client_id
            client_secret = self.settings.wyscout_client_secret
            if client_id and client_secret:
                token_raw = f"{client_id}:{client_secret}".encode("utf-8")
                basic_header = base64.b64encode(token_raw).decode("ascii")
                self.http.session.headers["Authorization"] = f"Basic {basic_header}"

        self.signed_http: Optional[HTTPClient] = None
        if (
            self.settings.wyscout_aws_access_key
            and self.settings.wyscout_aws_secret_key
            and self.settings.wyscout_aws_region
        ):
            self.signed_http = HTTPClient(
                self.settings.wyscout_base_url,
                auth_token=auth_token,
                aws_sigv4={
                    "access_key": self.settings.wyscout_aws_access_key,
                    "secret_key": self.settings.wyscout_aws_secret_key,
                    "region": self.settings.wyscout_aws_region,
                    "service": self.settings.wyscout_aws_service,
                },
            )
            if not auth_token and basic_header:
                self.signed_http.session.headers["Authorization"] = f"Basic {basic_header}"
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

    @staticmethod
    def _cache_suffix(params: Optional[Dict[str, Any]]) -> str:
        if not params:
            return "default"
        items = tuple(sorted(params.items()))
        return "_".join(f"{key}-{value}" for key, value in items)

    def list_areas(self, *, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch geographic areas supported by the API.
        """
        path = f"{self.settings.wyscout_api_version}/areas"
        payload = self._fetch(path, cache_key="wyscout_areas", use_cache=use_cache)
        if isinstance(payload, dict):
            areas = payload.get("areas")
            if isinstance(areas, list):
                return areas
        if isinstance(payload, list):
            return payload
        return []

    @staticmethod
    def common_area_index() -> List[Dict[str, Any]]:
        """
        Return a curated list of commonly used areas without hitting the API.
        """
        return [_clone_area_entry(area) for area in _COMMON_AREAS]

    @staticmethod
    def resolve_common_area(identifier: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        Resolve an identifier against the curated area index.
        """
        if identifier is None:
            return None
        if isinstance(identifier, int):
            for area in _COMMON_AREAS:
                if area["id"] == identifier:
                    return _clone_area_entry(area)
            return None
        norm = _normalize_area_key(identifier)
        if not norm:
            return None
        entry = _COMMON_AREA_LOOKUP.get(norm)
        if entry is None:
            return None
        return _clone_area_entry(entry)

    def resolve_area(
        self, identifier: Union[int, str], *, use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve an area identifier using the common index and, if needed, live data.
        """
        if identifier is None:
            return None
        entry = self.resolve_common_area(identifier)
        if entry is not None:
            return entry

        areas = self.list_areas(use_cache=use_cache)
        if isinstance(identifier, int):
            for area in areas:
                if area.get("id") == identifier:
                    return area
            return None

        norm = _normalize_area_key(identifier)
        for area in areas:
            candidates = {
                area.get("name"),
                area.get("alpha2code"),
                area.get("alpha3code"),
            }
            for token in candidates:
                if token and _normalize_area_key(str(token)) == norm:
                    return area
        return None

    def list_competitions(
        self, *, area_id: Optional[int] = None, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch available competitions.
        """
        path = f"{self.settings.wyscout_api_version}/competitions"
        params: Optional[Dict[str, Any]] = None
        if area_id is not None:
            params = {"areaId": area_id}
        cache_key = (
            f"wyscout_competitions_area_{area_id}" if area_id is not None else "wyscout_competitions"
        )
        payload = self._fetch(path, params=params, cache_key=cache_key, use_cache=use_cache)
        if isinstance(payload, dict):
            competitions = payload.get("competitions")
            if isinstance(competitions, list):
                return competitions
        if isinstance(payload, list):
            return payload
        return []

    def list_seasons(
        self, competition_id: int, *, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch seasons for a competition.
        """
        path = f"{self.settings.wyscout_api_version}/competitions/{competition_id}/seasons"
        cache_key = f"wyscout_competition_{competition_id}_seasons"
        payload = self._fetch(path, cache_key=cache_key, use_cache=use_cache)
        if isinstance(payload, dict):
            seasons = payload.get("seasons") or payload.get("competitionSeasons")
            if isinstance(seasons, list):
                return seasons
        if isinstance(payload, list):
            return payload
        return []

    def list_matches(
        self, competition_id: int, season_id: int, *, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch matches for a competition season.
        """
        path = f"{self.settings.wyscout_api_version}/games/competition/{competition_id}/season/{season_id}"
        cache_key = f"wyscout_matches_{competition_id}_{season_id}"
        payload = self._fetch(path, cache_key=cache_key, use_cache=use_cache)
        if isinstance(payload, dict):
            matches = payload.get("matches") or payload.get("games")
            if isinstance(matches, list):
                return matches
        if isinstance(payload, list):
            return payload
        return []

    def list_competition_players(
        self,
        competition_id: int,
        *,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch player list for a competition.
        """
        path = f"{self.settings.wyscout_api_version}/competitions/{competition_id}/players"
        cache_key = f"wyscout_players_{competition_id}_{self._cache_suffix(params)}"
        payload = self._fetch(path, params=params, cache_key=cache_key, use_cache=use_cache)
        if isinstance(payload, dict):
            players = payload.get("players")
            if isinstance(players, list):
                return players
        if isinstance(payload, list):
            return payload
        return []

    def get_events(
        self, match_id: int, *, use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch detailed event data for a game.
        """
        path = f"{self.settings.wyscout_api_version}/events/{match_id}"
        cache_key = f"wyscout_events_{match_id}"
        return self._fetch(path, cache_key=cache_key, use_cache=use_cache)

    def get_match_events(
        self,
        match_id: int,
        *,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Fetch match events via the matches endpoint.
        """
        path = f"{self.settings.wyscout_api_version}/matches/{match_id}/events"
        cache_key = f"wyscout_match_events_{match_id}_{self._cache_suffix(params)}"
        return self._fetch(path, params=params, cache_key=cache_key, use_cache=use_cache)

    def get_player_advanced_stats(
        self,
        player_id: int,
        *,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Fetch advanced statistics for a player.
        """
        path = f"{self.settings.wyscout_api_version}/players/{player_id}/advancedstats"
        cache_key = f"wyscout_player_adv_{player_id}_{self._cache_suffix(params)}"
        return self._fetch(path, params=params, cache_key=cache_key, use_cache=use_cache)

    def get_match_advanced_stats(
        self,
        match_id: int,
        *,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Fetch advanced statistics for a match.
        """
        path = f"{self.settings.wyscout_api_version}/matches/{match_id}/advancedstats"
        cache_key = f"wyscout_match_adv_{match_id}_{self._cache_suffix(params)}"
        return self._fetch(path, params=params, cache_key=cache_key, use_cache=use_cache)

    def get_match_players_advanced_stats(
        self,
        match_id: int,
        *,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Fetch advanced statistics for all players in a match.
        """
        path = f"{self.settings.wyscout_api_version}/matches/{match_id}/advancedstats/players"
        cache_key = f"wyscout_match_players_adv_{match_id}_{self._cache_suffix(params)}"
        return self._fetch(path, params=params, cache_key=cache_key, use_cache=use_cache)
