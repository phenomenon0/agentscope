## Visualization Attachments

### Added
- `_extract_tool_visualizations_from_memory()` in `agentspace/api/app.py` aggregates Base64 images and metadata from recent tool executions so `/api/agent/chat` responses surface visualization assets.
- Front-end `ChatPanel` now merges attachments returned by the API without injecting placeholder images; gallery rendering leverages real tool output exclusively.

### Updated
- `/api/agent/chat` merges attachments coming from the reply message and memory-derived tool outputs, ensuring metadata such as `viz_type`, match identifiers, and inline `images[]` arrays persist.
- `VisualizationGallery` continues rendering both inline Base64 strings and `/api/viz` paths and now receives only real attachments.
- Removed the hard-coded debug PNG once real tool imagery was confirmed.

### Verification
- Run `plot_event_heatmap_tool` (or any StatsBomb viz tool) for a completed fixture; the tool metadata now includes `images[]` with Base64 payloads that render in the chat UI without additional glue code.

## Season Ranking Pipeline

### Added
- `agentspace/analytics/season_summary_store.py` manages season summary ingestion, schema creation, percentile computation, and ingestion run logging. Includes helpers to resolve config/DB paths and ingest entire tracking configs.
- `scripts/update_season_summaries.py` CLI ingests tracked competitions into `.cache/season_summaries.db`, supports dry-run, config/database overrides, and cron-friendly logging.
- `agentspace/agent_tools/rankings.py` exposes cached leaderboards (`rank_players_by_metric_tool`), player percentile snapshots (`player_percentile_snapshot_tool`), coverage discovery (`list_ranking_coverage_tool`), and metric discovery (`list_ranking_metrics_tool`) under the new `season-rankings` tool group. Metric aliases (e.g. `progressive_passes`) map automatically to stored column names.
- Metric suite support: `config/ranking_suites.yml`, `list_ranking_suites_tool`, and `rank_players_by_suite_tool` allow bundled leaderboards (shooting, passing, pressing, defending, ball progression, goalkeeping) with composite percentiles.
- FastAPI endpoints `/api/leaderboards/players` and `/api/leaderboards/percentile` surface leaderboard Markdown and percentile summaries to UI consumers.
- Documentation: `docs/season-ranking-pipeline.md` outlines configuration, ingestion, toolkit/API usage, testing, and rollout guidance.

### Updated
- StatsBomb chat agents register the `season-rankings` toolkit and system prompts instruct personas to consult cached leaderboards before hitting network-heavy endpoints.
- `requirements.txt` now includes `PyYAML` for ingest configuration parsing.
- Season summary schema upgrades add missing columns (`position`, `primary_position`, `secondary_position`, `position_bucket`, `minutes`, `competition_name`, `metadata_json`) when older caches are detected, avoiding runtime errors against existing SQLite files.
- Popular competition aliases now recognise `Champions League`, `UCL`, `Europa League`, etc., and season ID mappings were added so the loader caches the last three seasons for Premier League, La Liga, Serie A, Ligue 1, UCL, UEL, UECL, FA Cup, Copa del Rey, Coppa Italia, and Coupe de France out of the box.

### Testing
- Added `tests/test_season_rankings.py` covering ingestion writes, toolkit responses, and the new API endpoints using a seeded SQLite cache.

## Offline SQLite Index Enhancements

### Added
- `agentspace/indexes/offline_sqlite_index.py` now builds a comprehensive SQLite database containing:
  - Top domestic leagues and continental cup competitions, seeded via explicit `CompetitionSpec` entries.
  - Teams and players populated from StatsBomb season aggregates.
  - Matches (`matches` table) with metadata (scores, teams, stadium, stage) filtered to completed fixtures, plus `match_players` rows that capture every appearance (starters and substitutes) extracted from lineups.
  - Full-text search (FTS5) tables for competitions, teams, and players to support fuzzy lookups.
- Dynamic season resolution:
  - Pulls latest seasons via `list_seasons`; falls back to `season_labels` (e.g. `2025/2026`, `2024/2025`, `2023/2024`, `2022/2023`) so only recent seasons are indexed.
  - Skips competitions lacking data while logging warnings.
- Configurable builder:
  - `CompetitionSpec` accepts `season_labels` per competition, enabling fine-grained control over historic coverage.
  - `OfflineIndexBuilder.build()` writes to `.cache/offline_index/top_competitions.sqlite` (or any provided path).

### Modified
- `agentspace/agent_tools/offline_sqlite.py`’
  - Simplified type annotations so the schema generator in AgentScope registers the tools without Pydantic errors.
  - Registers six primary tools (`offline_index_status`, `search_competitions_tool`, `search_teams_tool`, `search_players_tool`, `search_matches_tool`, `search_match_players_tool`) under the `offline-index` group.
  - Connection helper automatically points to the generated SQLite file and surfaces human-readable errors if the DB is missing.
  - `search_matches_tool` exposes fixture metadata; `search_match_players_tool` returns match-day lineups including substitutes.
  - Visualization tools now embed Base64 image data in every response (tool metadata includes `images[]` with `data`, `mime_type`, `alt`, and fallback `path`).
- `agentspace/agents/statsbomb_chat.py`
  - Imports and registers the offline toolkit, prioritising `offline-index` lookups before online or network tools in both analyst personas.
  - System prompts updated to instruct agents to use the offline index when available.
- Tests:
  - `tests/test_offline_sqlite_index.py` now uses a mock StatsBomb client that exercises the new builder workflow (competitions, teams, players, matches).
  - `tests/test_statsbomb_chat_agent.py` confirms the offline tool group is registered alongside existing StatsBomb integration.

### Known Limitations
- Some domestic cups (FA Cup, Copa del Rey, Coupe de France, etc.) do not expose player aggregates via the StatsBomb API; those competitions include teams and matches, but `players`/`match_players` entries may be sparse.
- Large competition lists can take several minutes to build; timeouts in the StatsBomb API are retried with logging but may require reruns for full coverage.

### How to Rebuild the Offline Index
```bash
python -m agentspace.indexes.offline_sqlite_index
```
or run with a custom competition list:
```python
from pathlib import Path
from agentspace.indexes.offline_sqlite_index import OfflineIndexBuilder, CompetitionSpec

builder = OfflineIndexBuilder(
    competitions=[
        CompetitionSpec("Premier League", "league", competition_id=2, max_seasons=4,
                        season_labels=("2025/2026","2024/2025","2023/2024","2022/2023")),
        # …additional competitions…
    ],
    db_path=Path(".cache/offline_index/top_competitions.sqlite"),
)
builder.build()
```

After rebuilding, restart the backend (or allow auto-reload) so both Analyst and Scouting agents immediately surface the new offline data through the `offline-index` tools.
