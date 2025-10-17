"""
Facade helpers for fetching football data.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional

from ..cache import DataCache
from ..config import APISettings
from ..exceptions import APIClientError
from ..clients.statsbomb import StatsBombClient
from ..clients.wyscout import WyscoutClient


@lru_cache(maxsize=1)
def _settings() -> APISettings:
    return APISettings.from_env()


@lru_cache(maxsize=1)
def _cache() -> DataCache:
    return DataCache(_settings().cache_dir)


@lru_cache(maxsize=1)
def _statsbomb_client() -> StatsBombClient:
    return StatsBombClient(settings=_settings(), cache=_cache())


@lru_cache(maxsize=1)
def _wyscout_client() -> WyscoutClient:
    return WyscoutClient(settings=_settings(), cache=_cache())


def get_statsbomb_client() -> StatsBombClient:
    """
    Return a cached StatsBomb client instance.
    """
    return _statsbomb_client()


def get_wyscout_client() -> WyscoutClient:
    """
    Return a cached Wyscout client instance.
    """
    return _wyscout_client()


def fetch_statsbomb_matches(competition_id: int, season_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve StatsBomb matches for a competition season.
    """
    return _statsbomb_client().list_matches(competition_id, season_id)


def fetch_statsbomb_events(match_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve StatsBomb events for a match.
    """
    return _statsbomb_client().get_events(match_id)


def fetch_statsbomb_360(match_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve StatsBomb 360 freeze frames.
    """
    return _statsbomb_client().get_360_frames(match_id)


def fetch_statsbomb_player_season_stats(
    competition_id: int,
    season_id: int,
    *,
    params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve StatsBomb player season aggregates.
    """
    return _statsbomb_client().get_player_season_stats(
        competition_id, season_id, params=params
    )


def fetch_wyscout_matches(competition_id: int, season_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve Wyscout matches for a competition season.
    """
    return _wyscout_client().list_matches(competition_id, season_id)


def fetch_wyscout_events(match_id: int) -> Dict[str, Any]:
    """
    Retrieve Wyscout event data for a match.
    """
    return _wyscout_client().get_events(match_id)


def get_match_ids(
    competitions: List[int], season_id: int, *, source: str = "statsbomb"
) -> List[int]:
    """
    Helper to gather match identifiers for competitions.
    """
    match_ids: List[int] = []
    for comp in competitions:
        if source == "statsbomb":
            matches = fetch_statsbomb_matches(comp, season_id)
        elif source == "wyscout":
            matches = fetch_wyscout_matches(comp, season_id)
        else:
            raise APIClientError(f"Unsupported data source '{source}'")
        for match in matches:
            identifier = match.get("match_id") or match.get("matchId")
            if identifier is not None:
                match_ids.append(identifier)
    return match_ids
