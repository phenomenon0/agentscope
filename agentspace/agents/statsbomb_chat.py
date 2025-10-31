"""Interactive Agentscope chat agent using StatsBomb toolkit."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

from requests.exceptions import RequestException

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentscope.agent import ReActAgent
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel, AnthropicChatModel
from agentscope.formatter import OpenAIChatFormatter, AnthropicChatFormatter
from agentscope.plan import PlanNotebook
from agentscope.tool import Toolkit

from agentspace import init_session_with_statsbomb_tools
from agentspace.agent_tools.index_lookup import register_statsbomb_index_tools
from agentspace.agent_tools.online_index import register_statsbomb_online_index_tools
from agentspace.agent_tools.offline_sqlite import register_offline_index_tools
from agentspace.agent_tools.viz import register_statsbomb_viz_tools
from agentspace.agent_tools.advanced_viz import register_advanced_viz_tools
from agentspace.agent_tools.event_analysis import register_event_analysis_tools
from agentspace.agent_tools.wyscout import register_wyscout_tools
from agentspace.agent_tools.web_search import register_web_search_tools


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


def _season_label_for_today(today: date) -> str:
    """
    Estimate the football season label corresponding to today's date.
    """
    start_year = today.year if today.month >= 7 else today.year - 1
    return f"{start_year}/{start_year + 1}"


def _system_prompt() -> str:
    """
    Build a dynamic system prompt that reflects current date context.
    """
    today = datetime.now(timezone.utc).astimezone()
    season_label = _season_label_for_today(today.date())
    current_year = today.year
    next_year = current_year + 1
    competition_reference = "\n".join(
        [
            "Competition reference (hard-coded):",
            "- Premier League — competition_id=2; season ids: 2025/26=318, 2024/25=317, 2023/24=281, 2022/23=235, 2021/22=108.",
            "- La Liga — competition_id=11; use list_seasons_tool if a season id is missing.",
            "- Bundesliga — competition_id=9.",
            "- Serie A — competition_id=12; fallback season id 318.",
            "- Ligue 1 — competition_id=7.",
            "- Eredivisie — competition_id=6.",
            "- Primeira Liga — competition_id=13.",
            "- Jupiler Pro League — competition_id=46.",
            "- MLS — competition_id=37.",
            "- UEFA Champions League — competition_id=16.",
            "- UEFA Europa League — competition_id=35.",
            "- UEFA Europa Conference League — competition_id=353.",
            "- FA Cup — competition_id=69.",
            "- Copa del Rey — competition_id=87.",
            "- Coppa Italia — competition_id=66.",
            "- Coupe de France — competition_id=86.",
            "- DFB Pokal — competition_id=165.",
            "- Danish Superliga — competition_id=77.",
            "- Allsvenskan — competition_id=75.",
            "- J1 League — competition_id=108.",
            "- 2. Bundesliga — competition_id=10.",
            "- Serie B — competition_id=1281.",
        ]
    )
    api_versions = (
        "StatsBomb API versions: competitions=v4, seasons=v6, matches=v6, events=v8, "
        "lineups=v4, 360=v2, player season stats=v4, team season stats=v2, "
        "player match stats=v5, team match stats=v1."
    )
    guidelines_lines = [
        "Guidelines:",
        "- Before any other lookup, default to the offline SQLite index for resolving identifiers.",
        "- For player, team, or match queries, use the offline SQLite helpers (`search_competitions_tool`, `search_teams_tool`, `search_players_tool`, `search_matches_tool`, `search_match_players_tool`) in the fastest logical combination before touching other tool families. Only move onward when those checks cannot supply the IDs you need.",
        "- Minimise tool calls: check existing metadata before reaching for another tool, and avoid repeating the same lookup with identical arguments.",
        "- Prefer aggregate helpers (season summaries, player lists) before drilling into match-level detail; only fetch full event datasets when required for deeper analysis.",
        "- Default to polished Markdown output with tasteful emoji section markers; only emit raw JSON when the user explicitly provides a template or demands JSON.",
        "- When offline coverage is insufficient, fall back in this order: StatsBomb JSON indices (group 'statsbomb-index'), StatsBomb online index helpers (group 'statsbomb-online-index'), then full network StatsBomb APIs.",
        "- StatsBomb online helpers include `list_seasons_online`, `find_player_online`, `find_team_players_online`, `get_player_matches_online`, and `resolve_player_current_team_online`; call them after exhausting the offline sequence.",
        "- If those still fail, use network StatsBomb tools, then Wyscout, then finally web search.",
        "- Wyscout tools (group 'wyscout') provide competition/season/match listings and event payloads; tap them when StatsBomb coverage is missing or to cross-check results.",
        "- Web search tools (group 'web') offer a lightweight DuckDuckGo proxy; use them as a secondary sanity check when official feeds disagree.",
        "- Only call web search after both StatsBomb online and offline lookups (including player mapping) fail to return relevant results; record why the fallback is required.",
        "- Wyscout access uses `WYSCOUT_ACCESS_TOKEN` or `WYSCOUT_CLIENT_ID`/`WYSCOUT_CLIENT_SECRET` from the environment when available.",
        "- Use network StatsBomb tools when detailed stats/events are required.",
        "- Always prefer relevant tools over guessing; cite data or explain when nothing is found.",
        "- Keep responses concise and structured, referencing key metrics or metadata.",
        "- Include tool results that matter (counts, top performers, etc.) in plain text summaries.",
        "- When a tool returns sample rows, parse those IDs (competition_id, season_id, match_id) before calling follow-up tools.",
        "- Avoid repeating the same tool call with identical arguments when an error occurs; adjust filters or explain the issue.",
        "- For player or team statistics, prefer `fetch_player_season_aggregates`, `fetch_team_season_aggregates`, or `fetch_player_match_aggregates`.",
        "- Use `list_team_players_tool` or `list_competition_players_tool` to resolve player ids, positions, and minutes before drilling into individual metrics.",
        "- When competition or season context is missing, resolve it (rather than assuming the Premier League) before calling summary tools.",
        f"- When you need match identifiers, call `list_team_matches` with `season_name` set to {season_label} (or the user-specified season) and `match_status=['played']` unless they explicitly want future fixtures.",
        "- Use `summarise_match_performance` for quick FotMob-style match overviews (player summaries, team totals, leaderboards).",
        "- Summarise final answers with key numbers and match identifiers so the user can verify the results.",
        "- Prefer the quick summary tools (`player_season_summary_tool`, `team_season_summary_tool`, `player_multi_season_summary_tool`, `compare_player_season_summaries_tool`) for straightforward stat requests.",
        "- Event filters support `event_types`, `team_name`, `opponent_name`, `player_names`, `possession_team_names`, `periods`, `minute_range`, `time_range`, `score_states`, `play_patterns`, `outcome_names`, and spatial `zone`.",
        "- When a requested season is missing from the cache, describe the fallback path instead of repeating the same failing lookup.",
        "Refer to the competition reference section below instead of firing extra lookups when it already covers the user's request.",
    ]
    guidelines = "\n".join(guidelines_lines)
    return (
        "You are a football data analyst with live access to StatsBomb's Data API via "
        "Agentspace tools. Use the provided tools to answer questions about competitions, "
        "seasons, matches, player statistics, team aggregates, and events.\n\n"
        f"Today's date: {today.strftime('%Y-%m-%d %H:%M %Z')} (current year {current_year}). "
        f"When users mention 'this season' default to {season_label} unless context dictates otherwise. "
        f"If a future season is referenced, consider {current_year}/{next_year} next.\n"
        f"{api_versions}\n"
        f"{guidelines}\n\n"
        f"{competition_reference}"
    )


def _scouting_system_prompt() -> str:
    today = datetime.now(timezone.utc).astimezone()
    current_year = today.year
    next_year = current_year + 1
    season_label = _season_label_for_today(today.date())
    competition_reference = "\n".join(
        [
            "Competition reference (hard-coded):",
            "- Premier League — competition_id=2; season ids: 2025/26=318, 2024/25=317, 2023/24=281, 2022/23=235, 2021/22=108.",
            "- La Liga — competition_id=11; use list_seasons_tool if a season id is missing.",
            "- Bundesliga — competition_id=9.",
            "- Serie A — competition_id=12; fallback season id 318.",
            "- Ligue 1 — competition_id=7.",
            "- Eredivisie — competition_id=6.",
            "- Primeira Liga — competition_id=13.",
            "- Jupiler Pro League — competition_id=46.",
            "- MLS — competition_id=37.",
            "- UEFA Champions League — competition_id=16.",
            "- UEFA Europa League — competition_id=35.",
            "- UEFA Europa Conference League — competition_id=353.",
            "- FA Cup — competition_id=69.",
            "- Copa del Rey — competition_id=87.",
            "- Coppa Italia — competition_id=66.",
            "- Coupe de France — competition_id=86.",
            "- DFB Pokal — competition_id=165.",
            "- Danish Superliga — competition_id=77.",
            "- Allsvenskan — competition_id=75.",
            "- J1 League — competition_id=108.",
            "- 2. Bundesliga — competition_id=10.",
            "- Serie B — competition_id=1281.",
        ]
    )
    modules = "\n".join(
        [
            "Mental profiling — evaluate mindset, resilience, decision focus.",
            "Team profiling — map the player's fit within team styles, emotional and tactical archetypes.",
            "Zones of Impact — chart where and how the player drives ball progression or control.",
            "Gravity-Angle analysis — assess how body orientation, angles, and gravity manipulation create advantages.",
            "Compact-speed analysis — judge tempo control, quickness of execution, and ability to operate in tight spaces.",
            "Dead-motion analysis — study athleticism in set-piece or stationary-to-explosive scenarios.",
        ]
    )
    profiling = (
        "Player profiling must consider Action range (what the player attempts and where), "
        "Athletic range (physical toolkit enabling those actions), and Execution range (quality, intensity, efficiency)."
    )
    outputs = "\n".join(
        [
            "- Provide comparisons (past or current players) grounded in role, traits, or data.",
            "- Suggest tactical deployment ideas, including combinations with current squad members.",
            "- Highlight risks, developmental needs, and squad-building implications.",
            "- Reference team context from metadata when available to ground recommendations.",
            "- Default to Markdown with section emojis (e.g., 🎯, 🧠, ⚙️)."
        ]
    )
    expectations_lines = [
        "- Before any deeper analysis, always start with the offline SQLite index. For player, team, or match work, apply the relevant combination of `search_competitions_tool`, `search_teams_tool`, `search_players_tool`, and `search_matches_tool`/`search_match_players_tool` to obtain IDs before touching other tool families.",
        "- Minimise tool calls: review existing context and combine StatsBomb queries so you extract what you need in one pass.",
        "- Use cached or aggregate helpers before drilling into per-match detail; avoid re-fetching the same dataset with identical arguments.",
        "- Lean on the offline SQLite index (group 'offline-index') for top league and continental cup rosters before issuing new API calls.",
        "- Gather evidence via StatsBomb tools first. If the offline sequence misses coverage, fall back to StatsBomb JSON indices, then StatsBomb online helpers, then network StatsBomb APIs before considering Wyscout or web search.",
        f"- When you need match identifiers, call `list_team_matches` with `season_name` set to {season_label} (or the user's specified season) and `match_status=['played']` unless they explicitly want future fixtures.",
        "- Never reach for web search until StatsBomb online/offline (including player mapping) options are exhausted and you've explained the gap.",
        "- Translate metrics into the six scouting modules, then synthesise into club-specific insights.",
        "- Evaluate the scouting club's current roster (from metadata) to judge fit, role competition, and tactical combinations.",
        "- Surface at least one positive comparison and one cautionary or developmental comp when data allows.",
        "- Comment on how performances may translate across leagues with differing physical demands.",
        "- Present insights in professional Markdown with emoji headers; no JSON unless the user explicitly requests it.",
        "- Use plan-and-act behaviour with tools; cite match IDs, seasons, and metrics.",
        "- Always explain reasoning when data is sparse, and propose follow-up scouting actions when confidence is low.",
        "Refer to the competition reference section below instead of firing extra lookups when it already answers the question.",
    ]
    expectations = "\n".join(expectations_lines)
    return (
        "You are an elite scouting strategist blending quantitative analysis with nuanced "
        "observational frameworks. Assess players comprehensively while referencing the "
        "recruiting team's current context.\n\n"
        f"Today's date: {today.strftime('%Y-%m-%d %H:%M %Z')} (current year {current_year}). "
        f"Use {season_label} as the active season by default; if discussions point to future projections, "
        f"consider {current_year}/{next_year}.\n\n"
        "Scouting modules to cover:\n"
        f"{modules}\n\n"
        f"{profiling}\n\n"
        "Expectations:\n"
        f"{expectations}\n"
        f"{outputs}\n\n"
        f"{competition_reference}"
    )


def _resolve_provider_and_model(
    *,
    model: str | None,
    provider: str | None,
) -> tuple[str, str]:
    """Resolve which provider/model to use based on args and env.

    Returns a tuple of (provider, model_name).

    Provider is one of: "anthropic", "openai".
    """
    env_provider = (provider or os.getenv("LLM_PROVIDER") or os.getenv("AGENTSPACE_LLM_PROVIDER") or "").strip().lower()
    candidate_model = (model or os.getenv("LLM_MODEL") or "").strip()

    # If model explicitly looks like a Claude family model or mentions opus/sonnet, pick Anthropic.
    m_lower = candidate_model.lower()
    if any(k in m_lower for k in ("claude", "opus", "sonnet")):
        env_provider = env_provider or "anthropic"

    # If provider still unspecified, infer from API keys present.
    if not env_provider:
        if os.getenv("ANTHROPIC_API_KEY"):
            env_provider = "anthropic"
        else:
            env_provider = "openai"

    if env_provider not in {"anthropic", "openai"}:
        raise ValueError(f"Unsupported LLM provider '{env_provider}'. Use 'anthropic' or 'openai'.")

    if not candidate_model:
        if env_provider == "anthropic":
            flavor = (os.getenv("CLAUDE_FLAVOR") or "sonnet").strip().lower()
            if flavor.startswith("opus"):
                candidate_model = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")
            elif flavor in {"sonnet-3.5", "sonnet3.5"}:
                candidate_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
            elif flavor.startswith("haiku"):
                candidate_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
            else:
                candidate_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        else:
            candidate_model = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Map friendly aliases
    alias_map = {
        "sonnet": "claude-sonnet-4-20250514",
        "sonnet-4": "claude-sonnet-4-20250514",
        "sonnet4": "claude-sonnet-4-20250514",
        "claude-sonnet-4": "claude-sonnet-4-20250514",
        "claude-sonnet-4-2025": "claude-sonnet-4-20250514",
        "sonnet-4.5": "claude-3-5-sonnet-20241022",
        "sonnet4.5": "claude-3-5-sonnet-20241022",
        "claude-3.5-sonnet-4.5": "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-4-5": "claude-3-5-sonnet-20241022",
        "sonnet-3.5": "claude-3-5-sonnet-20241022",
        "sonnet3.5": "claude-3-5-sonnet-20241022",
        "opus": "claude-3-opus-20240229",
    }
    candidate_model = alias_map.get(candidate_model.lower(), candidate_model)

    return env_provider, candidate_model


def _ensure_credentials() -> None:
    if not (os.getenv("STATSBOMB_USERNAME") or os.getenv("STATSBOMB_EMAIL")):
        raise RuntimeError(
            "StatsBomb credentials missing: set STATSBOMB_USERNAME or STATSBOMB_EMAIL."
        )
    if not os.getenv("STATSBOMB_PASSWORD"):
        raise RuntimeError("STATSBOMB_PASSWORD environment variable is required.")


def _resolve_backend_urls(
    *,
    studio_url: str | None = None,
    tracing_url: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Resolve AgentScope Studio and tracing endpoints from explicit args or env.
    """

    def _first_non_empty(values: Sequence[str | None]) -> str | None:
        for value in values:
            if not value:
                continue
            stripped = value.strip()
            if stripped:
                return stripped
        return None

    resolved_studio = _first_non_empty(
        [studio_url, os.getenv("AGENTSPACE_STUDIO_URL"), os.getenv("AGENTSCOPE_STUDIO_URL")]
    )
    resolved_tracing = _first_non_empty(
        [tracing_url, os.getenv("AGENTSPACE_TRACING_URL"), os.getenv("AGENTSCOPE_TRACING_URL")]
    )
    return resolved_studio, resolved_tracing


def _build_toolkit(
    project: str | None,
    activate_tool_group: bool,
    *,
    studio_url: str | None = None,
    tracing_url: str | None = None,
) -> Toolkit:
    resolved_studio, resolved_tracing = _resolve_backend_urls(
        studio_url=studio_url,
        tracing_url=tracing_url,
    )
    try:
        toolkit = init_session_with_statsbomb_tools(
            project=project,
            studio_url=resolved_studio,
            tracing_url=resolved_tracing,
            activate=activate_tool_group,
        )
    except RequestException as exc:
        logging.warning(
            "AgentScope Studio unavailable at %s (%s); proceeding without Studio/Tracing hooks.",
            resolved_studio,
            exc,
        )
        fallback_tracing: str | None = None
        if resolved_tracing and resolved_studio:
            studio_root = resolved_studio.rstrip("/")
            if not resolved_tracing.startswith(f"{studio_root}/"):
                fallback_tracing = resolved_tracing
        elif resolved_tracing:
            fallback_tracing = resolved_tracing

        toolkit = init_session_with_statsbomb_tools(
            project=project,
            studio_url=None,
            tracing_url=fallback_tracing,
            activate=activate_tool_group,
        )
    register_statsbomb_online_index_tools(toolkit, group_name="statsbomb-online-index", activate=True)
    register_offline_index_tools(toolkit, group_name="offline-index", activate=True)
    register_statsbomb_index_tools(toolkit, group_name="statsbomb-index", activate=True)
    register_wyscout_tools(toolkit, group_name="wyscout", activate=True)
    register_statsbomb_viz_tools(toolkit, group_name="statsbomb-viz", activate=True)
    register_advanced_viz_tools(toolkit, group_name="advanced-viz", activate=True)
    register_event_analysis_tools(toolkit, group_name="event-analysis", activate=True)
    register_web_search_tools(toolkit, group_name="web", activate=True)
    return toolkit


def _build_model_formatter(
    *,
    model: str | None,
    provider: str | None,
) -> tuple[AnthropicChatModel | OpenAIChatModel, AnthropicChatFormatter | OpenAIChatFormatter]:
    provider_resolved, model_name = _resolve_provider_and_model(model=model, provider=provider)

    if provider_resolved == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for provider 'anthropic'.")
        chat_model = AnthropicChatModel(model_name=model_name, api_key=api_key)
        formatter = AnthropicChatFormatter()
    else:
        chat_model = OpenAIChatModel(model_name=model_name, api_key=os.getenv("OPENAI_API_KEY"))
        formatter = OpenAIChatFormatter()
    return chat_model, formatter


def build_chat_agent(
    *,
    project: str | None = "statsbomb-chat",
    model: str | None = None,
    provider: str | None = None,
    openai_api_key: str | None = None,
    activate_tool_group: bool = True,
    studio_url: str | None = None,
    tracing_url: str | None = None,
) -> ReActAgent:
    """Create a ReAct agent wired to StatsBomb tools."""

    if openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", openai_api_key)

    repo_root = Path(__file__).resolve().parents[2]
    _load_env_from_file(repo_root / ".env")
    _ensure_credentials()

    toolkit = _build_toolkit(
        project,
        activate_tool_group,
        studio_url=studio_url,
        tracing_url=tracing_url,
    )
    chat_model, formatter = _build_model_formatter(model=model, provider=provider)

    plan_notebook = PlanNotebook(max_subtasks=6)

    return ReActAgent(
        name="statsbomb-analyst",
        sys_prompt=_system_prompt(),
        model=chat_model,
        formatter=formatter,
        toolkit=toolkit,
        plan_notebook=plan_notebook,
        max_iters=6,
    )


def build_scouting_agent(
    *,
    project: str | None = "statsbomb-scout",
    model: str | None = None,
    provider: str | None = None,
    openai_api_key: str | None = None,
    activate_tool_group: bool = True,
    studio_url: str | None = None,
    tracing_url: str | None = None,
) -> ReActAgent:
    """Create a scouting-forward agent with advanced evaluation frameworks."""

    if openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", openai_api_key)

    repo_root = Path(__file__).resolve().parents[2]
    _load_env_from_file(repo_root / ".env")
    _ensure_credentials()

    toolkit = _build_toolkit(
        project,
        activate_tool_group,
        studio_url=studio_url,
        tracing_url=tracing_url,
    )
    chat_model, formatter = _build_model_formatter(model=model, provider=provider)

    plan_notebook = PlanNotebook(max_subtasks=6)

    return ReActAgent(
        name="scouting-analyst",
        sys_prompt=_scouting_system_prompt(),
        model=chat_model,
        formatter=formatter,
        toolkit=toolkit,
        plan_notebook=plan_notebook,
        max_iters=6,
    )


def chat(
    messages: Sequence[str],
    *,
    project: str | None = "statsbomb-chat",
    model: str | None = None,
    provider: str | None = None,
    openai_api_key: str | None = None,
    studio_url: str | None = None,
    tracing_url: str | None = None,
) -> list[str]:
    """Convenience function to run a short scripted dialogue."""

    agent = build_chat_agent(
        project=project,
        model=model,
        provider=provider,
        openai_api_key=openai_api_key,
        studio_url=studio_url,
        tracing_url=tracing_url,
    )

    async def _run_dialog() -> list[str]:
        outputs: list[str] = []
        for turn, user_text in enumerate(messages, start=1):
            user_msg = Msg(
                name="user",
                role="user",
                content=user_text,
            )
            try:
                reply_msg = await agent.reply(user_msg)
                outputs.append(reply_msg.get_text_content() or "")
            except Exception as exc:  # pylint: disable=broad-except
                outputs.append(f"Agent execution error: {exc}")
                break
        return outputs

    return asyncio.run(_run_dialog())


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    import sys

    prompt = sys.argv[1] if len(sys.argv) > 1 else "List Arsenal matches vs Everton last season"
    answer = chat([prompt])[-1]
    print(answer)
