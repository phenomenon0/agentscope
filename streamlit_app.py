"""
Run a Streamlit chat UI for the StatsBomb agent.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import streamlit as st
from agentscope.message import Msg

from agentspace.agents.statsbomb_chat import build_chat_agent


def _load_env_from_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _ensure_agent() -> None:
    if "agent" not in st.session_state:
        repo_root = Path(__file__).resolve().parent
        _load_env_from_file(repo_root / ".env")
        st.session_state.agent = build_chat_agent()
        st.session_state.history = []


def _run_async(coro: asyncio.coroutine) -> Msg:
    return asyncio.run(coro)


st.set_page_config(page_title="StatsBomb Analyst Chat", page_icon="⚽", layout="centered")
st.title("⚽ StatsBomb Analyst Chat")

with st.sidebar:
    if st.button("Reset Conversation"):
        st.session_state.clear()
        st.experimental_rerun()
    st.markdown(
        "This assistant plans before acting and uses StatsBomb tools via your local credentials. "
        "Ensure `.env` contains `STATSBOMB_USERNAME`, `STATSBOMB_PASSWORD`, and `OPENAI_API_KEY` (or set environment variables)."
    )
    show_metadata = st.checkbox("Show latest response metadata", value=False)

_ensure_agent()

for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about competitions, seasons, player stats, etc."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        agent = st.session_state.agent
        reply_msg = _run_async(agent.reply(Msg(name="user", role="user", content=prompt)))
        reply_text = reply_msg.get_text_content() or "(no text content)"
        st.session_state.history.append({"role": "assistant", "content": reply_text})
        with st.chat_message("assistant"):
            st.markdown(reply_text)
            if show_metadata and reply_msg.metadata:
                st.write("Metadata:", reply_msg.metadata)
    except Exception as exc:  # pylint: disable=broad-except
        error_text = f"Agent execution error: {exc}"
        st.session_state.history.append({"role": "assistant", "content": error_text})
        with st.chat_message("assistant"):
            st.error(error_text)
