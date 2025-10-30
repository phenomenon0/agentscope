"""
FastAPI app exposing lightweight wrappers around Agentspace services.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agentscope.agent import ReActAgent
from agentscope.message import Msg
from agentscope.model import AnthropicChatModel

from agentspace.services.statsbomb_tools import (
    get_competition_players,
    get_player_season_summary,
    list_matches,
    season_id_for_label,
)
from agentspace.services.team_context import (
    get_team_context_cached,
    load_team_context,
    summarise_context_for_prompt,
)
from agentspace.agent_tools.web_search import web_search
from agentspace.agents.statsbomb_chat import build_chat_agent, build_scouting_agent
from agentspace.services.analytics360 import (
    collect_player_360_metrics,
    collect_team_360_metrics,
)


app = FastAPI(title="Agentspace API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

PersonaLiteral = Literal["Analyst", "Scouting Evaluator"]


@dataclass
class AgentSession:
    agent: ReActAgent
    persona: PersonaLiteral
    last_used: float


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    persona: PersonaLiteral
    message: str
    team_context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    metadata: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Dict[str, Any]]] = None


_chat_sessions: Dict[str, AgentSession] = {}
_session_locks: Dict[str, asyncio.Lock] = {}

SESSION_TTL_SECONDS = 60 * 60  # one hour
MAX_SESSIONS = 20


def _metadata_from_team_context(team_context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not team_context:
        return None
    return {
        "team_name": team_context.get("team_name"),
        "competition_name": team_context.get("competition_name"),
        "competition_id": team_context.get("competition_id"),
        "season_label": team_context.get("season_label"),
        "table_position": team_context.get("table_position"),
        "table_size": team_context.get("table_size"),
        "record": team_context.get("record"),
        "next_match": team_context.get("next_match"),
        "generated_at": team_context.get("generated_at"),
    }


def _attachments_from_msg(msg: Msg) -> List[Dict[str, Any]]:
    attachments: List[Dict[str, Any]] = []
    for block in getattr(msg, "content", []) or []:
        if not isinstance(block, Mapping):
            continue
        if block.get("type") != "image":
            continue
        source = block.get("source")
        if not isinstance(source, Mapping):
            continue
        source_type = source.get("type")
        alt = block.get("alt")
        if source_type == "base64":
            data = source.get("data")
            mime_type = source.get("media_type") or "image/png"
            if isinstance(data, str) and data:
                attachments.append(
                    {
                        "type": "image",
                        "src": f"data:{mime_type};base64,{data}",
                        "mime_type": mime_type,
                        "alt": alt,
                    }
                )
        elif source_type == "url":
            url = source.get("url")
            mime_type = source.get("media_type")
            if isinstance(url, str) and url:
                attachments.append(
                    {
                        "type": "image",
                        "src": url,
                        "mime_type": mime_type,
                        "alt": alt,
                    }
                )
    return attachments


def _merge_attachment_lists(*lists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for items in lists:
        for attachment in items or []:
            if not isinstance(attachment, Mapping):
                continue
            src = attachment.get("src")
            if not isinstance(src, str) or not src:
                continue
            path = attachment.get("path")
            key = f"{src}|{path or ''}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(dict(attachment))
    return merged


async def _extract_tool_visualizations_from_memory(
    agent: ReActAgent,
    max_lookback: int = 12,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    attachments: List[Dict[str, Any]] = []
    merged_metadata: Dict[str, Any] = {}
    seen_sources: set[str] = set()

    try:
        history = await agent.memory.get_memory()  # type: ignore[call-arg]
    except Exception as exc:  # pragma: no cover - memory failures should be non-fatal
        print(f"Warning: unable to read agent memory for visualizations: {exc}")
        return attachments, merged_metadata

    if not history:
        return attachments, merged_metadata

    # examine recent messages in reverse chronology (newest first)
    recent_messages = history[-max_lookback:]
    for hist_msg in reversed(recent_messages):
        metadata = getattr(hist_msg, "metadata", None)
        content = getattr(hist_msg, "content", None)

        def _add_src(src: Optional[str], *, mime: Optional[str] = None, alt: Optional[str] = None, path: Optional[str] = None) -> None:
            if not src or not isinstance(src, str):
                return
            key = f"{src}|{path or ''}"
            if key in seen_sources:
                return
            seen_sources.add(key)
            entry: Dict[str, Any] = {
                "type": "image",
                "src": src,
            }
            if mime:
                entry["mime_type"] = mime
            if alt:
                entry["alt"] = alt
            if path:
                entry["path"] = path
            attachments.append(entry)

        # Extract from metadata first – reliable indicator of visualization tools
        if isinstance(metadata, Mapping):
            if metadata.get("viz_type") or metadata.get("image_data") or metadata.get("images"):
                # Merge useful fields
                for key in (
                    "viz_type",
                    "team_name",
                    "opponent_name",
                    "match_id",
                    "competition_id",
                    "season_id",
                    "sample_size",
                    "total_shots",
                    "total_goals",
                    "edge_count",
                    "node_count",
                ):
                    if key in metadata and key not in merged_metadata:
                        merged_metadata[key] = metadata[key]

                # Inline base64 data
                image_data = metadata.get("image_data")
                if isinstance(image_data, str) and image_data:
                    mime = metadata.get("image_mime_type") or "image/png"
                    alt = metadata.get("viz_type")
                    _add_src(f"data:{mime};base64,{image_data}", mime=mime, alt=alt)

                image_path = metadata.get("image_path")
                if isinstance(image_path, str) and image_path:
                    normalized_path = image_path.replace("\\", "/")
                    alt = metadata.get("viz_type")
                    _add_src(f"/api/viz?path={normalized_path}", alt=alt, path=normalized_path)

                images_meta = metadata.get("images")
                if isinstance(images_meta, list):
                    merged_list = merged_metadata.setdefault("images", [])
                    for img_meta in images_meta:
                        if not isinstance(img_meta, Mapping):
                            continue
                        merged_list.append(dict(img_meta))
                        data = img_meta.get("data")
                        mime = img_meta.get("mime_type") or metadata.get("image_mime_type") or "image/png"
                        alt = img_meta.get("alt") or metadata.get("viz_type")
                        path_val = img_meta.get("path")
                        if isinstance(data, str) and data:
                            _add_src(f"data:{mime};base64,{data}", mime=mime, alt=alt)
                        elif isinstance(path_val, str) and path_val:
                            normalized_path = path_val.replace("\\", "/")
                            _add_src(f"/api/viz?path={normalized_path}", alt=alt, path=normalized_path)

        # Extract image blocks from the tool response content
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, Mapping) or block.get("type") != "image":
                    continue
                source = block.get("source")
                alt = block.get("alt")
                if not isinstance(source, Mapping):
                    continue
                source_type = source.get("type")
                if source_type == "base64":
                    data = source.get("data")
                    mime = source.get("media_type") or "image/png"
                    if isinstance(data, str) and data:
                        _add_src(f"data:{mime};base64,{data}", mime=mime, alt=alt)
                elif source_type == "url":
                    url = source.get("url")
                    mime = source.get("media_type")
                    if isinstance(url, str) and url:
                        _add_src(url, mime=mime, alt=alt)

    return attachments, merged_metadata


def _format_context_for_prompt(team_context: Optional[Dict[str, Any]]) -> str:
    if not team_context:
        return ""
    competition_name = team_context.get("competition_name")
    return summarise_context_for_prompt(
        team_context,
        competition_name=competition_name,
    )


def _plan_preview_system_prompt() -> str:
    return (
        "You are Claude 3 Haiku providing live planning narration for a StatsBomb analyst agent. "
        "Explain, in short present-tense phrases, how you will approach the request using the available tools. "
        "Keep the tone calm and professional. "
        "Only produce Markdown italics (wrap the entire text in *...*) and update the plan as new thoughts emerge. "
        "Do not mention that you are fast or lightweight. "
        "Stay under 80 words."
    )


def _plan_preview_user_prompt(message: str, team_context: Optional[Dict[str, Any]]) -> str:
    context_text = _format_context_for_prompt(team_context)
    if context_text:
        return f"{context_text}\n\nUser question:\n{message}"
    return message


def _prune_sessions(now: Optional[float] = None) -> None:
    timestamp = now or time.time()
    expired_ids = [
        session_id
        for session_id, session in _chat_sessions.items()
        if (timestamp - session.last_used) > SESSION_TTL_SECONDS
    ]
    for session_id in expired_ids:
        _chat_sessions.pop(session_id, None)
        _session_locks.pop(session_id, None)

    if len(_chat_sessions) <= MAX_SESSIONS:
        return

    sorted_sessions = sorted(
        _chat_sessions.items(),
        key=lambda item: item[1].last_used,
    )
    for session_id, _session in sorted_sessions:
        if len(_chat_sessions) <= MAX_SESSIONS:
            break
        _chat_sessions.pop(session_id, None)
        _session_locks.pop(session_id, None)


def _get_or_create_agent(session_id: str, persona: PersonaLiteral) -> ReActAgent:
    now = time.time()
    existing = _chat_sessions.get(session_id)
    if existing:
        if existing.persona == persona:
            existing.last_used = now
            return existing.agent
        _chat_sessions.pop(session_id, None)
        _session_locks.pop(session_id, None)

    agent = build_chat_agent() if persona == "Analyst" else build_scouting_agent()
    _chat_sessions[session_id] = AgentSession(agent=agent, persona=persona, last_used=now)
    _session_locks[session_id] = asyncio.Lock()
    _prune_sessions(now=now)
    return agent


def _get_session_lock(session_id: str) -> asyncio.Lock:
    lock = _session_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[session_id] = lock
    return lock


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/team/context")
def team_context(
    competition_id: int = Query(..., ge=1),
    season_label: str = Query(..., min_length=3),
    team_name: str = Query(..., min_length=2),
    refresh: bool = Query(False),
) -> Dict[str, Any]:
    try:
        context = get_team_context_cached(
            competition_id,
            season_label,
            team_name,
            refresh=refresh,
            use_cache=not refresh,
        )
    except Exception as exc:  # pragma: no cover - underlying services may raise various errors
        raise HTTPException(status_code=500, detail=f"Failed to load team context: {exc}") from exc
    if not context:
        raise HTTPException(status_code=404, detail="Team context not found.")
    return context


@app.get("/api/player/season-summary")
def player_season_summary(
    player_name: str = Query(..., min_length=2),
    season_label: str = Query(..., min_length=3),
    competition_id: Optional[int] = Query(None, ge=1),
    competition: Optional[str] = Query(None, min_length=2),
    min_minutes: float = Query(0.0, ge=0.0),
) -> Dict[str, Any]:
    try:
        summary = get_player_season_summary(
            player_name=player_name,
            season_label=season_label,
            competition_id=competition_id,
            competition_name=competition,
            min_minutes=min_minutes,
            use_cache=False,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to load player summary: {exc}") from exc
    if not summary:
        raise HTTPException(status_code=404, detail="Player summary not found.")
    return summary


@app.get("/api/player/report")
def player_report(
    player_name: str = Query(..., min_length=2),
    season_label: str = Query(..., min_length=3),
    competition_id: Optional[int] = Query(None, ge=1),
    competition: Optional[str] = Query(None, min_length=2),
    min_minutes: float = Query(0.0, ge=0.0),
) -> Dict[str, Any]:
    try:
        summary = get_player_season_summary(
            player_name=player_name,
            season_label=season_label,
            competition_id=competition_id,
            competition_name=competition,
            min_minutes=min_minutes,
            use_cache=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to build player report: {exc}") from exc

    if not summary:
        raise HTTPException(status_code=404, detail="Player report not found.")

    highlights: List[Dict[str, Any]] = []
    for metric, label in [
        ("player_season_minutes", "Minutes"),
        ("player_season_goals", "Goals"),
        ("player_season_assists", "Assists"),
        ("player_season_xg", "xG"),
        ("player_season_xa", "xA"),
        ("player_season_shots", "Shots"),
    ]:
        value = summary.get(metric)
        if value in (None, "", 0, 0.0):
            continue
        highlights.append({"label": label, "metric": metric, "value": value})

    return {
        "player_name": summary.get("player_name") or player_name,
        "team_name": summary.get("team_name"),
        "season_label": season_label,
        "competition_id": summary.get("competition_id") or competition_id,
        "highlights": highlights,
        "metrics": summary,
    }


@app.get("/api/analytics/360/team")
def analytics_team_360(
    competition_id: int = Query(..., ge=1),
    season_label: str = Query(..., min_length=3),
    team_id: Optional[int] = Query(None, ge=1),
    team_name: Optional[str] = Query(None, min_length=2),
    max_matches: int = Query(6, ge=1, le=20),
    refresh: bool = Query(False),
) -> Dict[str, Any]:
    try:
        return collect_team_360_metrics(
            competition_id=competition_id,
            season_label=season_label,
            team_id=team_id,
            team_name=team_name,
            max_matches=max_matches,
            refresh=refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to compute team 360 analytics: {exc}") from exc


@app.get("/api/analytics/360/player")
def analytics_player_360(
    competition_id: int = Query(..., ge=1),
    season_label: str = Query(..., min_length=3),
    team_id: Optional[int] = Query(None, ge=1),
    team_name: Optional[str] = Query(None, min_length=2),
    player_id: Optional[int] = Query(None, ge=1),
    player_name: Optional[str] = Query(None, min_length=2),
    max_matches: int = Query(6, ge=1, le=20),
    refresh: bool = Query(False),
) -> Dict[str, Any]:
    try:
        return collect_player_360_metrics(
            competition_id=competition_id,
            season_label=season_label,
            team_id=team_id,
            team_name=team_name,
            player_id=player_id,
            player_name=player_name,
            max_matches=max_matches,
            refresh=refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to compute player 360 analytics: {exc}") from exc


@app.get("/api/players")
def list_players(
    competition_id: int = Query(..., ge=1),
    season_label: str = Query(..., min_length=3),
    team_name: Optional[str] = Query(None),
    min_minutes: float = Query(0.0, ge=0.0),
) -> Dict[str, Any]:
    try:
        players = get_competition_players(
            competition_id=competition_id,
            season_label=season_label,
            team_name=team_name,
            min_minutes=min_minutes,
            use_cache=False,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to list players: {exc}") from exc
    return {
        "competition_id": competition_id,
        "season_label": season_label,
        "team_name": team_name,
        "players": players,
    }


@app.get("/api/matches")
def list_team_matches(
    competition_id: int = Query(..., ge=1),
    season_label: str = Query(..., min_length=3),
    team_name: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=1),
) -> Dict[str, Any]:
    try:
        season_id = season_id_for_label(competition_id, season_label, use_cache=False)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to resolve season: {exc}") from exc
    if season_id is None:
        raise HTTPException(status_code=404, detail="Season identifier not found.")
    try:
        matches = list_matches(
            competition_id,
            season_id,
            team_name=team_name,
            use_cache=False,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Failed to list matches: {exc}") from exc
    if limit is not None:
        matches = matches[:limit]
    return {
        "competition_id": competition_id,
        "season_label": season_label,
        "team_name": team_name,
        "matches": matches,
    }


@app.get("/api/web-search")
def web_search_endpoint(
    query: str = Query(..., min_length=3),
    max_chars: int = Query(1500, ge=100, le=5000),
) -> Dict[str, Any]:
    response = web_search(query, max_chars=max_chars)
    content_blocks: List[Dict[str, Any]] = response.content  # type: ignore[assignment]
    text = ""
    if content_blocks:
        first = content_blocks[0]
        text = first.get("text", "")
    return {
        "query": query,
        "text": text,
        "metadata": response.metadata,
    }


@app.post("/api/agent/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid4())
    agent = _get_or_create_agent(session_id, request.persona)
    lock = _get_session_lock(session_id)

    prompt = request.message.strip()
    context_text = _format_context_for_prompt(request.team_context)
    if context_text:
        prompt = f"{context_text}\n\nUser question:\n{prompt}"

    metadata = _metadata_from_team_context(request.team_context)

    async with lock:
        reply_msg = await agent.reply(
            Msg(
                name="user",
                role="user",
                content=prompt,
                metadata=metadata,
            )
        )
        tool_attachments, tool_metadata = await _extract_tool_visualizations_from_memory(agent)

    reply_text = reply_msg.get_text_content() or ""
    msg_attachments = _attachments_from_msg(reply_msg)
    attachments = _merge_attachment_lists(msg_attachments, tool_attachments)

    final_metadata: Dict[str, Any] = {}
    if isinstance(reply_msg.metadata, Mapping):
        final_metadata.update(reply_msg.metadata)
    if metadata:
        final_metadata.update(metadata)
    if tool_metadata:
        if "images" in tool_metadata and "images" in final_metadata:
            existing = final_metadata.get("images")
            incoming = tool_metadata.get("images")
            if isinstance(existing, list) and isinstance(incoming, list):
                existing.extend(incoming)
                tool_metadata = {k: v for k, v in tool_metadata.items() if k != "images"}
        final_metadata.update(tool_metadata)

    return ChatResponse(
        session_id=session_id,
        reply=reply_text,
        metadata=final_metadata or None,
        attachments=attachments or None,
    )


@app.post("/api/agent/plan-preview")
async def agent_plan_preview(request: ChatRequest) -> StreamingResponse:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY is required for plan preview streaming.",
        )

    model_name = os.getenv("AGENTSPACE_PREVIEW_MODEL", "claude-3-haiku-20240307")
    planner_model = AnthropicChatModel(
        model_name=model_name,
        api_key=api_key,
        max_tokens=256,
        stream=True,
    )

    system_prompt = _plan_preview_system_prompt()
    user_prompt = _plan_preview_user_prompt(request.message, request.team_context)

    async def event_stream():
        prefix = "data: *Planning with Claude Haiku...*\n\n"
        yield prefix
        last_text = ""
        try:
            stream = planner_model(
                messages=[
                    {
                        "role": "system",
                        "content": [{"type": "text", "text": system_prompt}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": user_prompt}],
                    },
                ],
            )
            async for chunk in stream:
                for block in chunk.content or []:
                    if block.get("type") != "text":
                        continue
                    text = block.get("text") or ""
                    if not text:
                        continue
                    if text.startswith(last_text):
                        delta = text[len(last_text) :]
                    else:
                        delta = text
                    delta = delta.strip()
                    if not delta:
                        continue
                    last_text = text
                    for line in delta.splitlines():
                        cleaned = line.strip()
                        if not cleaned:
                            continue
                        # Ensure italics by wrapping each update.
                        payload = cleaned
                        if not (payload.startswith("*") and payload.endswith("*")):
                            payload = f"*{payload}*"
                        yield f"data: {payload}\n\n"
        except Exception as exc:  # pragma: no cover - transient model/network faults
            yield f"data: *Plan preview error: {exc}*\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/agent/compress/{session_id}")
async def compress_agent_session(session_id: str, keep: int = Query(6, ge=2, le=12)) -> Dict[str, Any]:
    session = _chat_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    lock = _get_session_lock(session_id)
    agent = session.agent

    async with lock:
        history = await agent.memory.get_memory()
        if len(history) <= keep + 2:
            return {
                "status": "skipped",
                "reason": "History too short to compress.",
                "size": len(history),
            }

        stitched = []
        for msg in history[:-keep]:
            text = msg.get_text_content()
            if not text:
                continue
            stitched.append(f"{msg.role.title()}: {text.strip()}")
        summary_source = "\n".join(stitched)
        summary_text = await _summarise_history_text(summary_source)

        summary_msg = Msg(
            name="system",
            role="system",
            content=(
                "Conversation summary retained for context. Use this as background for follow-up questions.\n"
                f"{summary_text}"
            ),
        )

        await agent.memory.clear()
        await agent.memory.add(summary_msg, allow_duplicates=True)
        await agent.memory.add(history[-keep:], allow_duplicates=True)

        session.last_used = time.time()

    return {
        "status": "compressed",
        "summary": summary_text,
        "kept": keep,
        "dropped": len(history) - keep,
    }


@app.delete("/api/agent/chat/{session_id}")
def reset_agent_session(session_id: str) -> Dict[str, str]:
    removed = _chat_sessions.pop(session_id, None)
    _session_locks.pop(session_id, None)
    return {
        "session_id": session_id,
        "status": "reset" if removed else "not-found",
    }


@app.get("/")
def index() -> Dict[str, Any]:
    return {
        "name": "Agentspace API",
        "version": app.version,
        "endpoints": [
            "/api/health",
            "/api/team/context",
            "/api/player/season-summary",
            "/api/player/report",
            "/api/players",
            "/api/matches",
            "/api/web-search",
            "/api/analytics/360/team",
            "/api/analytics/360/player",
            "/api/agent/plan-preview",
            "/api/agent/compress/{session_id}",
            "/api/agent/chat",
            "/api/agent/chat/{session_id}",
        ],
    }
async def _summarise_history_text(text: str, *, max_tokens: int = 512) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or not text.strip():
        return text.strip() if text.strip() else "(no summary content)"

    model_name = os.getenv("AGENTSPACE_PREVIEW_MODEL", "claude-3-haiku-20240307")
    summariser = AnthropicChatModel(
        model_name=model_name,
        api_key=api_key,
        max_tokens=max_tokens,
        stream=False,
    )

    prompt = (
        "Summarise the following football analysis conversation into concise bullet points. "
        "Preserve key facts, requests, and commitments so the analyst can continue seamlessly."
    )

    response = await summariser(
        messages=[
            {
                "role": "system",
                "content": [{"type": "text", "text": prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "text", "text": text[:6000]}],
            },
        ]
    )

    chunks = []
    for block in getattr(response, "content", []) or []:
        if block.get("type") == "text" and block.get("text"):
            chunks.append(block["text"])
    summary = "\n".join(chunks).strip()
    return summary or text.strip()
