"""
Agentspace data retrieval package.
"""

from .config import APISettings
from .cache import DataCache
from .exceptions import APIClientError, APINotFoundError, APIRateLimitError
from .services.statsbomb_tools import TOP_COMPETITION_IDS

__all__ = [
    "APISettings",
    "DataCache",
    "APIClientError",
    "APINotFoundError",
    "APIRateLimitError",
    "register_statsbomb_tools",
    "init_session_with_statsbomb_tools",
    "register_offline_index_tools",
    "TOP_COMPETITION_IDS",
]


def __getattr__(name):
    if name in {
        "register_statsbomb_tools",
        "init_session_with_statsbomb_tools",
        "register_offline_index_tools",
    }:
        from .agent_tools import (  # type: ignore import cycles
            register_statsbomb_tools,
            init_session_with_statsbomb_tools,
            register_offline_index_tools,
        )

        values = {
            "register_statsbomb_tools": register_statsbomb_tools,
            "init_session_with_statsbomb_tools": init_session_with_statsbomb_tools,
            "register_offline_index_tools": register_offline_index_tools,
        }
        return values[name]
    raise AttributeError(f"module 'agentspace' has no attribute '{name}'")
