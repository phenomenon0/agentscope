# Season Ranking Pipeline

This guide documents the end-to-end workflow for building and consuming the cached
season ranking stack. It covers ingestion, configuration, API/tool access, and
operational best practices so the pipeline stays reproducible for the whole team.

---

## Overview

1. **StatsBomb APIs → Ingestion Script**
   - `scripts/update_season_summaries.py` retrieves player season aggregates via
     `fetch_player_season_stats_data`.
   - For every competition/season defined in `config/season_tracking.yml`, the script
     resolves `season_id`, filters by `min_minutes`, and records derived metrics plus
     percentile cohorts.
2. **Ingestion Script → SQLite Cache (`.cache/season_summaries.db`)**
   - Tables:
     - `player_season_summary`: baseline player row per competition/season.
     - `player_season_metric`: metric/value pairs (one per player/metric).
     - `player_metric_percentile`: cached percentile scores per cohort and metric.
     - `ingestion_runs`: audit trail with start/completion status.
   - Upsert semantics keep the cache current—percentiles are recalculated each run.
3. **Cache → Tools & API**
   - Toolkit functions `rank_players_by_metric_tool` and
     `player_percentile_snapshot_tool` read the cache through read-only SQLite
     connections (tool group `season-rankings`).
   - FastAPI endpoints (`/api/leaderboards/players`,
     `/api/leaderboards/percentile`) wrap the toolkit output for UI consumption.
4. **Agent/UI**
   - Analyst and Scouting personas call the ranking tools for “best X” prompts before
     hitting network-heavy event processing.
   - Frontend components can request shortlists, percentiles, or highlight badges via
     the new API endpoints.

---

## Configuration & Storage

- **Config file**: `config/season_tracking.yml`

  ```yaml
  tracked_competitions:
    - name: "Serie A"
      competition_id: 12
      seasons:
        - label: "2025/2026"
          min_minutes_percent: 0.2
          min_minutes_floor: 600
        - label: "2024/2025"
          min_minutes_percent: 0.2
          min_minutes_floor: 600
        - label: "2023/2024"
          min_minutes_percent: 0.2
          min_minutes_floor: 600
  ```

  *Notes*:
  - Use `min_minutes_percent` to express thresholds relative to the season leader (e.g. `0.2` keeps anyone with ≥20% of the current max minutes). Combine with `min_minutes_floor` (e.g. `600`) for sensible lower bounds. You can still supply explicit `min_minutes` and the ingestion pipeline will pick the loosest threshold that retains coverage.
  - `percentile_positions` defines cohort buckets; names feed the percentile suffix
    (`position:Defenders`) and should match strings passed to tooling.
  - Optional overrides: `season_id`, extra seasons, alternative buckets per season. Popular competitions (PL, La Liga, Serie A, Ligue 1, UCL, UEL) ship with season ID mappings for the last three campaigns, so multi-year ingestion works without manual IDs.

- **Environment overrides**
  - `AGENTSPACE_SEASON_DB` – custom SQLite path (defaults to `.cache/season_summaries.db`).
  - `AGENTSPACE_SEASON_CONFIG` – alternate config file (useful for staging/tests).

- **Schema contract**
  - `player_season_summary.last_updated` stores ISO timestamps (UTC).
  - Percentile cohorts rely on `cohort_key`, formatted as
    `<competition_id>:<season_id>:<suffix>` where `suffix` is `all` or
    `position:<BucketName>`.

---

## Ingestion Pipeline

- **Module**: `agentspace.analytics.season_summary_store`
  - Handles config parsing, schema creation, upserts, percentile computation, and
    ingestion run logging.
  - Percentiles computed with pure-Python percent rank logic per cohort.
  - Exposes helpers to resolve DB/config paths and to ingest entire configs.

- **Script**: `scripts/update_season_summaries.py`

  ```bash
  # Dry-run (no writes)
  python scripts/update_season_summaries.py --dry-run --log-level DEBUG

  # Targeted ingestion
  python scripts/update_season_summaries.py --competition 2 --log-level INFO
  ```

  | Flag | Purpose |
  | ---- | ------- |
  | `--config` | Override config location. |
  | `--database` | Override output SQLite file. |
  | `--competition / -c` | Restrict to specific competition(s) (name or ID). |
  | `--dry-run` | Fetch and compute without persisting updates. |
  | `--log-level` | Adjust logging verbosity. |

- **Automation**:
  - Example cron: `0 3 * * * /path/to/update_season_summaries.py --log-level INFO >> /var/log/season_ingest.log 2>&1`
  - Document manual backfills for historic seasons (run script with explicit `--competition` and custom config including old `season_id`s).
  - CI recommendation: run `python scripts/update_season_summaries.py --dry-run` to ensure API compatibility.

---

## Ranking Tools & API

- **Toolkit module**: `agentspace/agent_tools/rankings.py`
  - `list_ranking_coverage_tool`: enumerate competitions/seasons currently cached.
  - `list_ranking_metrics_tool`: list available metric columns for a given season/competition (aliases such as `progressive_passes`, `shots_on_target`, `carries_90`, etc. map automatically).
  - `list_ranking_suites_tool`: discover pre-defined metric bundles (shooting, passing, pressing, defending, ball progression, aerial duels, crossing, ball recovery, retention, goalkeeping).
  - `rank_players_by_metric_tool`: Markdown leaderboard + metadata (metric values, percentiles, minutes) with automatic metric name normalisation.
  - `rank_players_by_suite_tool`: Multi-metric leaderboard with per-metric percentiles and composite score.
  - `player_percentile_snapshot_tool`: Bullet summary of metrics/percentiles for a player.
  - Register via `register_ranking_tools(toolkit, group_name="season-rankings")`.

- **FastAPI endpoints**
  - `/api/leaderboards/players`
    - Query params: `metric` (alias `metric_name`), `season_label`, `competitions`,
      `limit`, `sort_order`, `min_minutes`, `position_bucket`.
    - Returns `{description, table, metadata}`; raises 404 when cache is empty.
  - `/api/leaderboards/percentile`
    - Query params: `season_label`, `player_id` or `player_name`, optional
      `competition_id`/`competitions`, `limit`, `position_bucket`.
    - Returns summary line, bullet list text, and structured metadata.

- **Agent integration**
  - Tool group `season-rankings` registered alongside existing StatsBomb/Wyscout tools.
  - System prompts now enforce a tool hierarchy: coverage/metrics → ranking tools for "best" queries, offline index for ID resolution, aggregates for summaries, then heavyweight APIs only if the cache is empty.

---

## Testing Strategy

- Unit tests cover:
  - Ingestion (percentile computation + upserts against mocked StatsBomb rows).
  - Toolkit functions (leaderboard + snapshot filtering).
  - API endpoints (FastAPI `TestClient` with temp SQLite cache).
- Integration smoke:
  - Run script in `--dry-run --log-level DEBUG` to verify logging and API compatibility.
  - Manual command to ingest a single competition and validate API outputs.
- Regression guard:
  - CI workflow: `pytest` + `python scripts/update_season_summaries.py --dry-run`.

---

## Rollout Checklist

1. Implement modules, script, and tests (merge when green).
2. Run ingestion locally to populate cache; keep SQLite out of source control unless explicitly required.
3. Confirm agent prompt/toolkit updates operate as expected (chat persona should mention cached rankings).
4. Deploy backend and run ingestion job once in the target environment.
5. Coordinate frontend work to consume `/api/leaderboards/*`.
6. Monitor ingestion logs and API 500s post-deploy; review `ingestion_runs` table for failures.

---

## Troubleshooting

- **404 from leaderboard endpoints** → cache missing. Re-run ingestion and ensure
  `AGENTSPACE_SEASON_DB` points to the correct path.
- **`database_error` metadata** → SQLite file corrupt/inaccessible; inspect logs and
  consider rebuilding.
- **Percentile bucket returns nulls** → verify the bucket name matches the config
  (case-sensitive) and players satisfy `min_minutes`.
- **Agent not using rankings** → ensure personas restarted after deployment (hot reload
  or service restart) so the new tool group and prompt are loaded.
