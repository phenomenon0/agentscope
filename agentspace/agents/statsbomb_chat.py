"""Interactive Agentscope chat agent using StatsBomb toolkit."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentscope.agent import ReActAgent
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel
from agentscope.formatter import OpenAIChatFormatter
from agentscope.plan import PlanNotebook

from agentspace import init_session_with_statsbomb_tools


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


SYSTEM_PROMPT = """
You are a football data analyst with live access to StatsBomb's Data API via
Agentspace tools. Use the provided tools to answer questions about competitions,
seasons, matches, player statistics, team aggregates, and events.

Guidelines:
- Always prefer relevant tools over guessing; cite data or explain when nothing is found.
- Keep responses concise and structured, referencing key metrics or metadata.
- Include tool results that matter (counts, top performers, etc.) in plain text summaries.
- When a tool returns sample rows, parse those IDs (competition_id, season_id, match_id) before calling follow-up tools.
- Avoid repeating the same tool call with identical arguments when an error occurs; adjust filters or explain the issue.
- For player or team statistics, prefer `fetch_player_season_aggregates`, `fetch_team_season_aggregates`, or `fetch_player_match_aggregates`.
- Summarise final answers with key numbers and match identifiers so the user can verify the results.
- Prefer the quick summary tools (`player_season_summary_tool`, `team_season_summary_tool`, `player_multi_season_summary_tool`, `compare_player_season_summaries_tool`) for straightforward stat requests.
- Competition cheat sheet: Premier League (competition_id=2; seasons 2025/26=318, 2024/25=317, 2023/24=281, 2022/23=235, 2021/22=108). Top leagues include La Liga (11), Serie A (9), Bundesliga (12), Ligue 1 (13).
- When a requested season is not found in the cache, explain the fallback path rather than repeating the same failing lookup.
""".strip()


def build_chat_agent(
    *,
    project: str | None = "statsbomb-chat",
    model: str | None = None,
    openai_api_key: str | None = None,
    activate_tool_group: bool = True,
) -> ReActAgent:
    """Create a ReAct agent wired to StatsBomb tools."""

    if openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", openai_api_key)

    repo_root = Path(__file__).resolve().parents[2]
    _load_env_from_file(repo_root / ".env")

    if not (os.getenv("STATSBOMB_USERNAME") or os.getenv("STATSBOMB_EMAIL")):
        raise RuntimeError(
            "StatsBomb credentials missing: set STATSBOMB_USERNAME or STATSBOMB_EMAIL."
        )
    if not os.getenv("STATSBOMB_PASSWORD"):
        raise RuntimeError("STATSBOMB_PASSWORD environment variable is required.")

    toolkit = init_session_with_statsbomb_tools(
        project=project,
        activate=activate_tool_group,
    )

    chat_model = OpenAIChatModel(
        model_name=model or "gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    formatter = OpenAIChatFormatter()

    plan_notebook = PlanNotebook(
        max_subtasks=3,
    )

    agent = ReActAgent(
        name="statsbomb-analyst",
        sys_prompt=SYSTEM_PROMPT,
        model=chat_model,
        formatter=formatter,
        toolkit=toolkit,
        plan_notebook=plan_notebook,
    )

    return agent


def chat(
    messages: Sequence[str],
    *,
    project: str | None = "statsbomb-chat",
    model: str | None = None,
    openai_api_key: str | None = None,
) -> list[str]:
    """Convenience function to run a short scripted dialogue."""

    agent = build_chat_agent(
        project=project,
        model=model,
        openai_api_key=openai_api_key,
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
