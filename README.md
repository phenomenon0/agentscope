# Agentspace Workspace

This repository now contains:

1. **FastAPI service** (`agentspace/api/app.py`) that exposes the existing StatsBomb/Wyscout helpers as HTTP endpoints (team context, player summaries, roster lists, match lists, web search proxy).
2. **Next.js + AI SDK workspace** (`frontend/`) that streams Markdown-first answers from either the *Analyst* or *Scouting Evaluator* persona while keeping the club dashboard visible alongside the chat.

## Running locally

### Python API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn agentspace.api.app:app --reload
```

### Next.js workspace

```bash
cd frontend
npm install
npm run dev
```

Create `.env.local` if required:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SEASON_LABEL=2025/2026
```

Open <http://localhost:3000>. Switch personas from the sidebar, pick a preset team (Arsenal, Manchester United, Bournemouth), and the assistant will automatically pull the latest context before answering.

## Tests

```bash
pytest
```

## Notes

- FastAPI now exposes `/api/agent/chat`, which proxies persona requests to the Agentscope agent and maintains per-session memory.
- The Next.js API route simply forwards chat turns to the FastAPI backend, so no LLM API keys are required on the frontend.
- Use the new `build_scouting_agent` helper if you want to run the advanced persona directly from Python.
- To mirror every tool call in AgentScope Studio, export `AGENTSPACE_STUDIO_URL` (or `AGENTSCOPE_STUDIO_URL`) before starting the backend; optionally provide `AGENTSPACE_TRACING_URL`/`AGENTSCOPE_TRACING_URL` to forward OpenTelemetry traces.
- Visualization helpers now rely on `mplsoccer` (`statsbomb-viz` tool group). Export `AGENTSPACE_VIZ_DIR` to control where PNGs are written; the agents will automatically attach paths when you call `plot_match_shot_map_tool`, `plot_event_heatmap_tool`, or `plot_pass_network_tool`.
- Build the offline SQLite index for the top leagues and continental cups with `python -m agentspace.indexes.offline_sqlite_index`; register it inside AgentScope via `register_offline_index_tools(toolkit, db_path=".cache/offline_index/top_competitions.sqlite")` to enable super-fast competition, team, and player lookups without hitting the network.
