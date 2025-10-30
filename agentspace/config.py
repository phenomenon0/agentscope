"""
Configuration helpers for API clients.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_ENV_LOADED = False


def _ensure_env_loaded() -> None:
    """
    Load environment variables from a .env file if present.
    """
    global _ENV_LOADED  # noqa: PLW0603 - intentional module level state
    if _ENV_LOADED:
        return

    candidates = []
    explicit = os.getenv("AGENTSPACE_ENV_FILE")
    if explicit:
        candidates.append(Path(explicit))
    cwd_env = Path.cwd() / ".env"
    candidates.append(cwd_env)
    repo_env = Path(__file__).resolve().parents[1] / ".env"
    if repo_env != cwd_env:
        candidates.append(repo_env)

    for path in candidates:
        if not path or not path.exists():
            continue
        try:
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except OSError:
            continue

    _ENV_LOADED = True


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
    wyscout_aws_access_key: Optional[str]
    wyscout_aws_secret_key: Optional[str]
    wyscout_aws_region: Optional[str]
    wyscout_aws_service: Optional[str]
    cache_dir: str
    # Optional: Player mapping API lives on a different host; defaults provided.
    statsbomb_player_mapping_base_url: str = "https://data.statsbomb.com/api"
    statsbomb_player_mapping_version: str = "v1"

    @classmethod
    def from_env(cls) -> "APISettings":
        """
        Construct settings using environment variables with sensible defaults.
        """
        _ensure_env_loaded()
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
            statsbomb_player_mapping_base_url=os.getenv(
                "STATSBOMB_PLAYER_MAPPING_BASE_URL", "https://data.statsbomb.com/api"
            ),
            statsbomb_player_mapping_version=os.getenv(
                "STATSBOMB_PLAYER_MAPPING_VERSION", "v1"
            ),
            wyscout_base_url=os.getenv(
                "WYSCOUT_BASE_URL", "https://apirest.wyscout.com"
            ),
            wyscout_token=os.getenv("WYSCOUT_ACCESS_TOKEN")
            or os.getenv("WYSCOUT_TOKEN"),
            wyscout_client_id=os.getenv("WYSCOUT_CLIENT_ID")
            or os.getenv("WYSCOUT_ID"),
            wyscout_client_secret=os.getenv("WYSCOUT_CLIENT_SECRET")
            or os.getenv("WYSCOUT_SECRET"),
            wyscout_api_version=os.getenv("WYSCOUT_API_VERSION", "v4"),
            wyscout_aws_access_key=os.getenv("WYSCOUT_AWS_ACCESS_KEY")
            or os.getenv("WYSCOUT_ID")
            or os.getenv("WYSCOUT_CLIENT_ID"),
            wyscout_aws_secret_key=os.getenv("WYSCOUT_AWS_SECRET_KEY")
            or os.getenv("WYSCOUT_SECRET")
            or os.getenv("WYSCOUT_CLIENT_SECRET"),
            wyscout_aws_region=os.getenv("WYSCOUT_AWS_REGION"),
            wyscout_aws_service=os.getenv("WYSCOUT_AWS_SERVICE", "execute-api"),
            cache_dir=os.getenv("AGENTSPACE_CACHE_DIR", ".cache"),
        )
