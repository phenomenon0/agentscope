"""
Lightweight fallback web search tool using read-only HTTP fetch.
"""
from __future__ import annotations

import html
import re
from typing import Optional
from urllib.parse import quote_plus

import requests
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse, Toolkit


def _clean_text(raw: str) -> str:
    text = html.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def web_search(query: str, *, max_chars: int = 1500) -> ToolResponse:
    """
    Perform a lightweight web lookup via a text-only proxy.
    """

    if not query.strip():
        return ToolResponse(
            content=[TextBlock(type="text", text="Web search query must not be empty.")],
            metadata={"query": query, "results": None},
        )

    endpoint = f"https://r.jina.ai/https://duckduckgo.com/?q={quote_plus(query)}"
    try:
        response = requests.get(endpoint, timeout=15)
        response.raise_for_status()
        body = response.text
    except Exception as exc:  # pragma: no cover - network dependencies
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Web search failed: {exc}")],
            metadata={"query": query, "results": None},
        )

    cleaned = _clean_text(body)[:max_chars]
    if not cleaned:
        cleaned = "No readable content returned from search proxy."
    metadata = {"query": query, "results": cleaned}
    return ToolResponse(
        content=[TextBlock(type="text", text=cleaned)],
        metadata=metadata,
    )


def register_web_search_tools(toolkit: Optional[Toolkit] = None, *, group_name: str = "web", activate: bool = True) -> Toolkit:
    toolkit = toolkit or Toolkit()
    try:
        toolkit.create_tool_group(
            group_name,
            description="Lightweight web search fallback.",
            active=activate,
            notes="Proxy-powered text search useful for quick cross-checks.",
        )
    except ValueError:
        pass

    toolkit.register_tool_function(
        web_search,
        group_name=group_name,
        func_description="Fetch plain-text search results for a query (uses DuckDuckGo proxy).",
    )
    return toolkit
