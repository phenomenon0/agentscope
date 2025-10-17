"""
Configuration helpers for API clients.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class APISettings:
    """
    Runtime configuration for remote API clients.
    """

    statsbomb_base_url: str
    statsbomb_token: Optional[str]
    statsbomb_email: Optional[str]
    statsbomb_password: Optional[str]
    statsbomb_competitions_version: str
    statsbomb_matches_version: str
    statsbomb_events_version: str
    statsbomb_lineups_version: str
    statsbomb_360_version: str
    statsbomb_player_stats_version: str
    statsbomb_team_stats_version: str
    statsbomb_seasons_version: str
    statsbomb_player_match_stats_version: str
    statsbomb_team_match_stats_version: str
    wyscout_base_url: str
    wyscout_token: Optional[str]
    wyscout_client_id: Optional[str]
    wyscout_client_secret: Optional[str]
    wyscout_api_version: str
    cache_dir: str

    @classmethod
    def from_env(cls) -> "APISettings":
        """
        Construct settings using environment variables with sensible defaults.
        """
        return cls(
            statsbomb_base_url=os.getenv(
                "STATSBOMB_BASE_URL", "https://data.statsbombservices.com/api"
            ),
            statsbomb_token=os.getenv("STATSBOMB_ACCESS_TOKEN"),
            statsbomb_email=os.getenv("STATSBOMB_EMAIL")
            or os.getenv("STATSBOMB_USERNAME"),
            statsbomb_password=os.getenv("STATSBOMB_PASSWORD"),
            statsbomb_competitions_version=os.getenv(
                "STATSBOMB_COMPETITIONS_VERSION",
                os.getenv("STATSBOMB_API_VERSION", "v4"),
            ),
            statsbomb_matches_version=os.getenv("STATSBOMB_MATCHES_VERSION", "v6"),
            statsbomb_events_version=os.getenv("STATSBOMB_EVENTS_VERSION", "v8"),
            statsbomb_lineups_version=os.getenv("STATSBOMB_LINEUPS_VERSION", "v4"),
            statsbomb_360_version=os.getenv("STATSBOMB_360_VERSION", "v2"),
            statsbomb_player_stats_version=os.getenv(
                "STATSBOMB_PLAYER_STATS_VERSION", "v4"
            ),
            statsbomb_team_stats_version=os.getenv(
                "STATSBOMB_TEAM_STATS_VERSION", "v2"
            ),
            statsbomb_seasons_version=os.getenv(
                "STATSBOMB_SEASONS_VERSION", "v6"
            ),
            statsbomb_player_match_stats_version=os.getenv(
                "STATSBOMB_PLAYER_MATCH_STATS_VERSION", "v5"
            ),
            statsbomb_team_match_stats_version=os.getenv(
                "STATSBOMB_TEAM_MATCH_STATS_VERSION", "v1"
            ),
            wyscout_base_url=os.getenv(
                "WYSCOUT_BASE_URL", "https://apirest.wyscout.com"
            ),
            wyscout_token=os.getenv("WYSCOUT_ACCESS_TOKEN"),
            wyscout_client_id=os.getenv("WYSCOUT_CLIENT_ID"),
            wyscout_client_secret=os.getenv("WYSCOUT_CLIENT_SECRET"),
            wyscout_api_version=os.getenv("WYSCOUT_API_VERSION", "v1"),
            cache_dir=os.getenv("AGENTSPACE_CACHE_DIR", ".cache"),
        )
