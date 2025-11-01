"""
FastAPI application exposing Agentspace data services.
"""

__all__ = ["app"]


def __getattr__(name):
    if name == "app":
        from .app import app as _app

        return _app
    raise AttributeError(f"module 'agentspace.api' has no attribute '{name}'")
