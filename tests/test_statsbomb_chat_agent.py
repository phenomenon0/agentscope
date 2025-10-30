"""
Tests for Agentspace chat agent configuration helpers.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

import agentspace.agents.statsbomb_chat as statsbomb_chat


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Ensure Studio-related env vars do not leak between tests.
    """

    for key in (
        "AGENTSPACE_STUDIO_URL",
        "AGENTSCOPE_STUDIO_URL",
        "AGENTSPACE_TRACING_URL",
        "AGENTSCOPE_TRACING_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_build_toolkit_resolves_studio_and_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    _build_toolkit should forward Studio/tracing endpoints resolved from env/kwargs.
    """

    captured: Dict[str, Any] = {}
    dummy_toolkit = object()

    def fake_init_session_with_statsbomb_tools(**kwargs: Any) -> object:
        captured.update(kwargs)
        return dummy_toolkit

    register_calls: list[str] = []

    def passthrough(toolkit: object, **kwargs: Any) -> object:
        group = kwargs.get("group_name")
        if group:
            register_calls.append(group)
        return toolkit

    monkeypatch.setattr(
        statsbomb_chat,
        "init_session_with_statsbomb_tools",
        fake_init_session_with_statsbomb_tools,
    )
    monkeypatch.setattr(statsbomb_chat, "register_statsbomb_online_index_tools", passthrough)
    monkeypatch.setattr(statsbomb_chat, "register_statsbomb_index_tools", passthrough)
    monkeypatch.setattr(statsbomb_chat, "register_offline_index_tools", passthrough)
    monkeypatch.setattr(statsbomb_chat, "register_wyscout_tools", passthrough)
    monkeypatch.setattr(statsbomb_chat, "register_statsbomb_viz_tools", passthrough)
    monkeypatch.setattr(statsbomb_chat, "register_web_search_tools", passthrough)

    monkeypatch.setenv("AGENTSPACE_STUDIO_URL", " http://studio.local ")
    monkeypatch.setenv("AGENTSCOPE_TRACING_URL", "http://trace.local")

    toolkit = statsbomb_chat._build_toolkit(project="proj", activate_tool_group=True)

    assert toolkit is dummy_toolkit
    assert captured["studio_url"] == "http://studio.local"
    assert captured["tracing_url"] == "http://trace.local"
    assert "offline-index" in register_calls
    assert "statsbomb-viz" in register_calls

    captured.clear()
    register_calls.clear()

    toolkit = statsbomb_chat._build_toolkit(
        project=None,
        activate_tool_group=False,
        studio_url="https://override",
        tracing_url=" https://trace-override ",
    )

    assert toolkit is dummy_toolkit
    assert captured["studio_url"] == "https://override"
    assert captured["tracing_url"] == "https://trace-override"
    assert "offline-index" in register_calls
    assert "statsbomb-viz" in register_calls


def test_build_chat_agent_uses_plan_max_subtasks(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    build_chat_agent should construct a PlanNotebook with max_subtasks=8.
    """

    captured: Dict[str, Any] = {}

    class DummyPlanNotebook:
        def __init__(self, *, max_subtasks: int | None = None, **_: Any) -> None:
            captured["max_subtasks"] = max_subtasks

    class DummyAgent:
        def __init__(self, **kwargs: Any) -> None:
            captured["agent_kwargs"] = kwargs

    monkeypatch.setattr(statsbomb_chat, "PlanNotebook", DummyPlanNotebook)
    monkeypatch.setattr(statsbomb_chat, "_build_toolkit", lambda *_, **__: object())
    monkeypatch.setattr(statsbomb_chat, "_build_model_formatter", lambda *_, **__: (object(), object()))
    monkeypatch.setattr(statsbomb_chat, "ReActAgent", DummyAgent)
    monkeypatch.setattr(statsbomb_chat, "_ensure_credentials", lambda: None)
    monkeypatch.setattr(statsbomb_chat, "_load_env_from_file", lambda *_: None)

    statsbomb_chat.build_chat_agent()

    assert captured["max_subtasks"] == 6
    assert isinstance(captured["agent_kwargs"]["plan_notebook"], DummyPlanNotebook)
    assert captured["agent_kwargs"]["max_iters"] == 6


def test_build_scouting_agent_uses_plan_max_subtasks(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    build_scouting_agent should construct a PlanNotebook with max_subtasks=8.
    """

    captured: Dict[str, Any] = {}

    class DummyPlanNotebook:
        def __init__(self, *, max_subtasks: int | None = None, **_: Any) -> None:
            captured.setdefault("max_subtasks", []).append(max_subtasks)

    class DummyAgent:
        def __init__(self, **kwargs: Any) -> None:
            captured["agent_kwargs"] = kwargs

    monkeypatch.setattr(statsbomb_chat, "PlanNotebook", DummyPlanNotebook)
    monkeypatch.setattr(statsbomb_chat, "_build_toolkit", lambda *_, **__: object())
    monkeypatch.setattr(statsbomb_chat, "_build_model_formatter", lambda *_, **__: (object(), object()))
    monkeypatch.setattr(statsbomb_chat, "ReActAgent", DummyAgent)
    monkeypatch.setattr(statsbomb_chat, "_ensure_credentials", lambda: None)
    monkeypatch.setattr(statsbomb_chat, "_load_env_from_file", lambda *_: None)

    statsbomb_chat.build_scouting_agent()

    assert captured["max_subtasks"] == [6]
    assert isinstance(captured["agent_kwargs"]["plan_notebook"], DummyPlanNotebook)
    assert captured["agent_kwargs"]["max_iters"] == 6
