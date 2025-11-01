"""
AgentScope tools exposing cached player season rankings and percentile snapshots.
"""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from agentscope.message import TextBlock
from agentscope.tool import Toolkit, ToolResponse

from agentspace.analytics.season_summary_store import resolve_db_path


@dataclass
class _RankingQueryResult:
    player_id: int
    player_name: str
    team_name: Optional[str]
    competition_id: int
    competition_name: Optional[str]
    season_label: str
    position: Optional[str]
    primary_position: Optional[str]
    secondary_position: Optional[str]
    position_bucket: Optional[str]
    minutes: float
    metric_value: float
    percentile: Optional[float]
    cohort_key: Optional[str]


def _open_connection(db_path: Optional[str]) -> sqlite3.Connection:
    resolved = resolve_db_path(Path(db_path) if db_path else None)
    if not resolved.exists():
        raise FileNotFoundError(
            f"Season summaries database not found at {resolved}. "
            "Run scripts/update_season_summaries.py to populate the cache."
        )
    conn = sqlite3.connect(f"file:{resolved.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


_METRIC_ALIASES = {
    "progressive_passes": "player_season_progressive_passes",
    "progressive_passes_90": "player_season_progressive_passes_90",
    "progressive_passes_per90": "player_season_progressive_passes_90",
    "progressive_passes_per_90": "player_season_progressive_passes_90",
    "final_third_entries": "player_season_final_third_entries",
    "passes_completed": "player_season_complete_passes",
    "passes_completed_90": "player_season_complete_passes_90",
    "passes_attempted": "player_season_total_passes",
    "passes_attempted_90": "player_season_total_passes_90",
    "passes_completed": "player_season_complete_passes",
    "passes_completed_per90": "player_season_complete_passes_90",
    "passes_completed_90": "player_season_complete_passes_90",
    "assist_90": "player_season_assists_90",
    "assists": "player_season_assists_90",
    "key_passes": "player_season_key_passes_90",
    "key_passes_90": "player_season_key_passes_90",
    "progressive_carries": "player_season_carries_90",
    "carries_90": "player_season_carries_90",
    "carry_length": "player_season_carry_length",
    "carry_ratio": "player_season_carry_ratio",
    "crosses_90": "player_season_crosses_90",
    "crossing_ratio": "player_season_crossing_ratio",
    "box_cross_ratio": "player_season_box_cross_ratio",
    "pressures": "player_season_pressures_90",
    "pressures_90": "player_season_pressures_90",
    "counterpressures": "player_season_counterpressures_90",
    "pressure_regains": "player_season_pressure_regains_90",
    "padj_pressures": "player_season_padj_pressures_90",
    "padj_tackles_interceptions": "player_season_padj_tackles_and_interceptions_90",
    "interceptions": "player_season_interceptions_90",
    "clearances": "player_season_clearance_90",
    "ball_recoveries": "player_season_ball_recoveries_90",
    "aggressive_actions": "player_season_aggressive_actions_90",
    "aerial_ratio": "player_season_aerial_ratio",
    "aerial_wins": "player_season_aerial_wins_90",
    "challenge_ratio": "player_season_challenge_ratio",
    "conversion_ratio": "player_season_conversion_ratio",
    "shots_touch_ratio": "player_season_shot_touch_ratio",
    "deep_progressions": "player_season_deep_progressions_90",
    "obv_carry": "player_season_obv_dribble_carry_90",
    "obv_pass": "player_season_obv_pass_90",
    "obv_shot": "player_season_obv_shot_90",
    "xag": "player_season_expected_assists",
    "xa": "player_season_expected_assists",
    "xa_90": "player_season_expected_assists_90",
    "assists_90": "player_season_assists_90",
    "assists_per90": "player_season_assists_90",
    "shots_on_target": "player_season_shot_on_target_ratio",
    "shots_on_target_ratio": "player_season_shot_on_target_ratio",
    "shot_on_target_ratio": "player_season_shot_on_target_ratio",
    "shots_on_target_90": "player_season_np_shots_90",
    "shots_on_target_per90": "player_season_np_shots_90",
    "shots": "player_season_np_shots_90",
    "shots_90": "player_season_np_shots_90",
    "shots_per90": "player_season_np_shots_90",
    "npxg": "player_season_non_penalty_xg",
    "npxg_90": "player_season_non_penalty_xg_90",
}


COMPETITION_ALIASES: Dict[str, int] = {
    "premier league": 2,
    "english premier league": 2,
    "england premier league": 2,
    "epl": 2,
    "la liga": 11,
    "laliga": 11,
    "spanish la liga": 11,
    "serie a": 12,
    "italian serie a": 12,
    "ligue 1": 7,
    "french ligue 1": 7,
    "champions league": 16,
    "uefa champions league": 16,
    "ucl": 16,
    "championsleague": 16,
    "europa league": 35,
    "uefa europa league": 35,
    "uel": 35,
    "europaleague": 35,
}


def _normalise_metric_name(metric_name: str) -> str:
    canonical = metric_name.strip().lower().replace(" ", "_")
    if canonical in _METRIC_ALIASES:
        return _METRIC_ALIASES[canonical]
    return metric_name


DEFAULT_METRIC_SUITES: Dict[str, Dict[str, Any]] = {
    "shooting": {
        "metrics": [
            "player_season_np_shots_90",
            "player_season_shot_on_target_ratio",
            "player_season_np_xg_90",
            "player_season_conversion_ratio",
        ],
        "primary_metric": "player_season_np_shots_90",
    },
    "passing": {
        "metrics": [
            "player_season_op_passes_90",
            "player_season_pass_completion_rate",
            "player_season_progressive_passes",
            "player_season_op_xa_90",
        ],
        "primary_metric": "player_season_op_passes_90",
    },
    "chance_creation": {
        "metrics": [
            "player_season_key_passes_90",
            "player_season_op_key_passes_90",
            "player_season_op_xa_90",
            "player_season_sp_xa_90",
        ],
        "primary_metric": "player_season_key_passes_90",
    },
    "pressing": {
        "metrics": [
            "player_season_pressures_90",
            "player_season_counterpressures_90",
            "player_season_pressure_regains_90",
            "player_season_padj_pressures_90",
        ],
        "primary_metric": "player_season_pressures_90",
    },
    "defending": {
        "metrics": [
            "player_season_padj_tackles_and_interceptions_90",
            "player_season_interceptions_90",
            "player_season_clearance_90",
            "player_season_blocks_per_shot",
        ],
        "primary_metric": "player_season_padj_tackles_and_interceptions_90",
    },
    "ball_progression": {
        "metrics": [
            "player_season_carries_90",
            "player_season_deep_progressions_90",
            "player_season_obv_dribble_carry_90",
            "player_season_op_xgbuildup_90",
        ],
        "primary_metric": "player_season_carries_90",
    },
    "goalkeeping": {
        "metrics": [
            "player_season_save_ratio",
            "player_season_gsaa_90",
            "player_season_np_psxg_90",
            "player_season_ot_shots_faced_ratio",
        ],
        "primary_metric": "player_season_save_ratio",
    },
    "aerial_duels": {
        "metrics": [
            "player_season_aerial_ratio",
            "player_season_aerial_wins_90",
            "player_season_challenge_ratio",
            "player_season_blocks_per_shot",
        ],
        "primary_metric": "player_season_aerial_wins_90",
    },
    "crossing": {
        "metrics": [
            "player_season_crosses_90",
            "player_season_crossing_ratio",
            "player_season_box_cross_ratio",
            "player_season_passes_into_box_90",
        ],
        "primary_metric": "player_season_crosses_90",
    },
    "ball_recovery": {
        "metrics": [
            "player_season_ball_recoveries_90",
            "player_season_aggressive_actions_90",
            "player_season_pressure_regains_90",
            "player_season_counterpressures_90",
        ],
        "primary_metric": "player_season_ball_recoveries_90",
    },
    "retention": {
        "metrics": [
            "player_season_turnovers_90",
            "player_season_dispossessions_90",
            "player_season_failed_dribbles_90",
            "player_season_dribble_ratio",
        ],
        "primary_metric": "player_season_dribble_ratio",
    },
}


def _parse_competition_filters(competitions: Optional[str]) -> Tuple[List[int], List[str]]:
    if not competitions:
        return [], []
    ids: List[int] = []
    names: List[str] = []
    seen_ids: set[int] = set()
    for token in competitions.split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        alias_match = COMPETITION_ALIASES.get(lowered) or COMPETITION_ALIASES.get(lowered.replace(" ", ""))
        if alias_match is not None:
            if alias_match not in seen_ids:
                ids.append(alias_match)
                seen_ids.add(alias_match)
            continue
        if cleaned.isdigit():
            value = int(cleaned)
            if value not in seen_ids:
                ids.append(value)
                seen_ids.add(value)
            continue
        names.append(lowered)
    return ids, names


@lru_cache(maxsize=1)
def _load_metric_suites() -> Dict[str, Dict[str, Any]]:
    path = Path("config/ranking_suites.yml")
    suites: Dict[str, Dict[str, Any]] = {}
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text()) or {}
            for name, spec in data.items():
                if not isinstance(spec, dict):
                    continue
                metrics = spec.get("metrics") or []
                if not metrics:
                    continue
                suites[name.lower()] = {
                    "metrics": list(metrics),
                    "primary_metric": spec.get("primary_metric"),
                }
        except (OSError, yaml.YAMLError):  # pragma: no cover - config optional
            suites = {}
    if not suites:
        suites = {key: dict(value) for key, value in DEFAULT_METRIC_SUITES.items()}
    return suites


def _resolve_cohort_suffix(conn: sqlite3.Connection, bucket: Optional[str]) -> str:
    if not bucket:
        return "all"
    target = bucket.strip().lower()
    rows = conn.execute(
        """
        SELECT DISTINCT
            substr(cohort_key, instr(cohort_key, ':position:') + length(':position:')) AS bucket_name
        FROM player_metric_percentile
        WHERE cohort_key LIKE '%:position:%'
        """
    ).fetchall()
    for row in rows:
        name = row["bucket_name"]
        if name and name.lower() == target:
            return f"position:{name}"
    # Fallback to user-provided bucket
    return f"position:{bucket.strip()}"


def _display_metric_name(metric: str) -> str:
    friendly_map = {
        "player_season_np_shots_90": "NP Shots/90",
        "player_season_shot_on_target_ratio": "Shot On Target %",
        "player_season_np_xg_90": "NP xG/90",
        "player_season_conversion_ratio": "Conversion %",
        "player_season_op_passes_90": "OP Passes/90",
        "player_season_pass_completion_rate": "Pass Completion %",
        "player_season_progressive_passes": "Progressive Passes",
        "player_season_op_xa_90": "OP xA/90",
        "player_season_passes_completed": "Passes Completed",
        "player_season_passes_completed_per_90": "Passes Completed/90",
        "player_season_key_passes_90": "Key Passes/90",
        "player_season_op_key_passes_90": "OP Key Passes/90",
        "player_season_sp_xa_90": "Set Piece xA/90",
        "player_season_pressures_90": "Pressures/90",
        "player_season_counterpressures_90": "Counterpressures/90",
        "player_season_pressure_regains_90": "Pressure Regains/90",
        "player_season_padj_pressures_90": "Adj. Pressures/90",
        "player_season_padj_tackles_and_interceptions_90": "Adj. T+I/90",
        "player_season_interceptions_90": "Interceptions/90",
        "player_season_clearance_90": "Clearances/90",
        "player_season_blocks_per_shot": "Blocks per Shot",
        "player_season_carries_90": "Carries/90",
        "player_season_deep_progressions_90": "Deep Progressions/90",
        "player_season_obv_dribble_carry_90": "OBV Carry/90",
        "player_season_op_xgbuildup_90": "OP xG Buildup/90",
        "player_season_save_ratio": "Save %",
        "player_season_gsaa_90": "GSAA/90",
        "player_season_np_psxg_90": "NP PSxG/90",
        "player_season_ot_shots_faced_ratio": "OT Shots Faced %",
        "player_season_aerial_ratio": "Aerial Win %",
        "player_season_aerial_wins_90": "Aerial Wins/90",
        "player_season_challenge_ratio": "Challenge Win %",
        "player_season_crosses_90": "Crosses/90",
        "player_season_crossing_ratio": "Crossing %",
        "player_season_box_cross_ratio": "Box Cross %",
        "player_season_passes_into_box_90": "Passes Into Box/90",
        "player_season_ball_recoveries_90": "Ball Recoveries/90",
        "player_season_aggressive_actions_90": "Aggressive Actions/90",
        "player_season_turnovers_90": "Turnovers/90",
        "player_season_dispossessions_90": "Dispossessions/90",
        "player_season_failed_dribbles_90": "Failed Dribbles/90",
        "player_season_dribble_ratio": "Dribble Success %",
    }
    if metric in friendly_map:
        return friendly_map[metric]
    if metric.startswith("player_season_"):
        short = metric[len("player_season_"):]
    else:
        short = metric
    return short.replace("_", " ").title()


def _metric_exists(conn: sqlite3.Connection, metric_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM player_season_metric WHERE metric_name = ? LIMIT 1",
        (metric_name,),
    ).fetchone()
    return row is not None


def _render_markdown_table(rows: Iterable[_RankingQueryResult], metric_name: str) -> str:
    lines = [
        f"| # | Player | Team | Competition | Metric | Percentile | Minutes |",
        "|---|--------|------|-------------|--------|------------|---------|",
    ]
    for idx, row in enumerate(rows, start=1):
        percentile = "—"
        if row.percentile is not None:
            percentile = f"{row.percentile:.1f}"
        team = row.team_name or "—"
        competition = row.competition_name or str(row.competition_id)
        lines.append(
            "| {rank} | {player} ({position}) | {team} | {competition} | {value:.3f} | {percentile} | {minutes:.0f} |".format(
                rank=idx,
                player=row.player_name,
                position=row.position or "—",
                team=team,
                competition=competition,
                value=row.metric_value,
                percentile=percentile,
                minutes=row.minutes,
            )
        )
    header = f"**Leaderboard — {metric_name}**"
    return "\n".join([header, "", *lines])


def _format_snapshot_bullets(records: Sequence[Tuple[str, float, Optional[float]]]) -> str:
    if not records:
        return "No percentile data available."
    lines = ["Key metrics and percentiles:"]
    for metric_name, value, percentile in records:
        if percentile is None:
            lines.append(f"- {metric_name}: {value:.3f} (percentile n/a)")
        else:
            lines.append(f"- {metric_name}: {value:.3f} (percentile {percentile:.1f})")
    return "\n".join(lines)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any((row[1] if isinstance(row, tuple) else row["name"]) == column for row in rows)


def rank_players_by_metric_tool(
    metric_name: str,
    season_label: str,
    competitions: Optional[str] = None,
    limit: int = 10,
    sort_order: str = "desc",
    min_minutes: Optional[float] = None,
    position_bucket: Optional[str] = None,
    db_path: Optional[str] = None,
) -> ToolResponse:
    if not metric_name:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="Metric name is required. Provide the exact metric column stored in the season cache.",
                )
            ],
            metadata={"error": "missing_metric"},
        )

    metric_name = _normalise_metric_name(metric_name)
    order_clause = "DESC" if str(sort_order).lower() != "asc" else "ASC"
    comp_ids, comp_names = _parse_competition_filters(competitions)

    try:
        with closing(_open_connection(db_path)) as conn:
            if not _metric_exists(conn, metric_name):
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text=(
                                f"Metric '{metric_name}' is not present in the ranking cache. "
                                "Call list_ranking_metrics_tool to inspect available metrics."
                            ),
                        )
                    ],
                    metadata={"error": "missing_metric", "metric": metric_name},
                )
            cohort_suffix = _resolve_cohort_suffix(conn, position_bucket)
            has_position_col = _column_exists(conn, "player_season_summary", "position")
            position_select = "s.position" if has_position_col else "NULL"
            primary_position_select = "s.primary_position" if _column_exists(conn, "player_season_summary", "primary_position") else "NULL"
            secondary_position_select = "s.secondary_position" if _column_exists(conn, "player_season_summary", "secondary_position") else "NULL"
            bucket_select = "s.position_bucket" if _column_exists(conn, "player_season_summary", "position_bucket") else "NULL"
            minutes_column = "s.minutes" if _column_exists(conn, "player_season_summary", "minutes") else "COALESCE(s.player_season_minutes, s.minutes_played, 0)"
            where_clauses = ["s.season_label = ?"]
            where_params: List[Any] = [season_label]
            if comp_ids:
                placeholders = ",".join("?" for _ in comp_ids)
                where_clauses.append(f"s.competition_id IN ({placeholders})")
                where_params.extend(comp_ids)
            if comp_names:
                placeholders = ",".join("?" for _ in comp_names)
                where_clauses.append(f"LOWER(s.competition_name) IN ({placeholders})")
                where_params.extend(comp_names)
            minutes_filter_expr = minutes_column
            if min_minutes is not None:
                where_clauses.append(f"{minutes_filter_expr} >= ?")
                where_params.append(float(min_minutes))
            if position_bucket:
                where_clauses.append("p.percentile IS NOT NULL")

            sql = f"""
                SELECT
                    s.player_id,
                    s.player_name,
                    s.team_name,
                    s.competition_id,
                    s.competition_name,
                    s.season_label,
                    {position_select} AS position,
                    {primary_position_select} AS primary_position,
                    {secondary_position_select} AS secondary_position,
                    {bucket_select} AS position_bucket,
                    {minutes_column} AS minutes,
                    m.metric_value,
                    p.percentile,
                    p.cohort_key
                FROM player_season_summary AS s
                JOIN player_season_metric AS m
                  ON m.competition_id = s.competition_id
                 AND m.season_id = s.season_id
                 AND m.player_id = s.player_id
                 AND m.metric_name = ?
                LEFT JOIN player_metric_percentile AS p
                  ON p.competition_id = s.competition_id
                 AND p.season_id = s.season_id
                 AND p.player_id = s.player_id
                 AND p.metric_name = ?
                 AND p.cohort_key = (CAST(s.competition_id AS TEXT) || ':' || CAST(s.season_id AS TEXT) || ':' || ?)
                WHERE {' AND '.join(where_clauses)}
                ORDER BY m.metric_value {order_clause}, minutes DESC
                LIMIT ?
            """
            params: List[Any] = [metric_name, metric_name, cohort_suffix, *where_params, int(limit)]
            rows = conn.execute(sql, params).fetchall()
    except FileNotFoundError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=str(exc))],
            metadata={"error": "missing_database"},
        )
    except sqlite3.DatabaseError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Season rankings cache unreadable: {exc}")],
            metadata={"error": "database_error"},
        )

    results: List[_RankingQueryResult] = []
    for row in rows:
        results.append(
            _RankingQueryResult(
                player_id=row["player_id"],
                player_name=row["player_name"],
                team_name=row["team_name"],
                competition_id=row["competition_id"],
                competition_name=row["competition_name"],
                season_label=row["season_label"],
                position=row["position"],
                primary_position=row["primary_position"],
                secondary_position=row["secondary_position"],
                position_bucket=row["position_bucket"],
                minutes=row["minutes"],
                metric_value=row["metric_value"],
                percentile=row["percentile"],
                cohort_key=row["cohort_key"],
            )
        )

    if not results:
        description = (
            "No cached season ranking data found for the requested parameters. "
            "Ensure the ingestion script has run and the metric/filters exist in the cache."
        )
        return ToolResponse(
            content=[TextBlock(type="text", text=description)],
            metadata={"results": [], "metric": metric_name},
        )

    markdown = _render_markdown_table(results, metric_name)
    metadata_results = [
        {
            "player_id": row.player_id,
            "player_name": row.player_name,
            "team_name": row.team_name,
            "competition_id": row.competition_id,
            "competition_name": row.competition_name,
            "season_label": row.season_label,
            "position": row.position,
            "primary_position": row.primary_position,
            "secondary_position": row.secondary_position,
            "position_bucket": row.position_bucket,
            "minutes": row.minutes,
            "metric_value": row.metric_value,
            "percentile": row.percentile,
            "cohort_key": row.cohort_key,
        }
        for row in results
    ]
    return ToolResponse(
        content=[TextBlock(type="text", text=markdown)],
        metadata={
            "metric": metric_name,
            "results": metadata_results,
            "season_label": season_label,
            "cohort_suffix": cohort_suffix,
        },
    )


def player_percentile_snapshot_tool(
    player_name: Optional[str] = None,
    player_id: Optional[int] = None,
    season_label: Optional[str] = None,
    competition_id: Optional[int] = None,
    competitions: Optional[str] = None,
    limit: int = 12,
    position_bucket: Optional[str] = None,
    db_path: Optional[str] = None,
) -> ToolResponse:
    if not season_label:
        return ToolResponse(
            content=[TextBlock(type="text", text="season_label is required to fetch a percentile snapshot.")],
            metadata={"error": "missing_season"},
        )
    if not player_id and not player_name:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="Provide player_id or player_name when requesting a percentile snapshot.",
                )
            ],
            metadata={"error": "missing_player"},
        )

    comp_ids, comp_names = _parse_competition_filters(competitions)
    if competition_id is not None:
        comp_ids.append(int(competition_id))

    missing_metrics: List[str] = []
    try:
        with closing(_open_connection(db_path)) as conn:
            cohort_suffix = _resolve_cohort_suffix(conn, position_bucket)
            has_position_col = _column_exists(conn, "player_season_summary", "position")
            position_select = "s.position" if has_position_col else "NULL AS position"
            minutes_column = "s.minutes" if _column_exists(conn, "player_season_summary", "minutes") else "COALESCE(s.player_season_minutes, s.minutes_played, 0)"
            clauses = ["s.season_label = ?"]
            params: List[Any] = [season_label]
            if player_id is not None:
                clauses.append("s.player_id = ?")
                params.append(int(player_id))
            if player_name:
                clauses.append("LOWER(s.player_name) = ?")
                params.append(player_name.strip().lower())
            if comp_ids:
                placeholders = ",".join("?" for _ in comp_ids)
                clauses.append(f"s.competition_id IN ({placeholders})")
                params.extend(comp_ids)
            if comp_names:
                placeholders = ",".join("?" for _ in comp_names)
                clauses.append(f"LOWER(s.competition_name) IN ({placeholders})")
                params.extend(comp_names)

            sql = f"""
                SELECT
                    s.player_id,
                    s.player_name,
                    s.team_name,
                    {position_select} AS position,
                    {minutes_column} AS minutes,
                    s.competition_id,
                    s.competition_name,
                    m.metric_name,
                    m.metric_value,
                    p.percentile
                FROM player_season_summary AS s
                JOIN player_season_metric AS m
                  ON m.competition_id = s.competition_id
                 AND m.season_id = s.season_id
                 AND m.player_id = s.player_id
                LEFT JOIN player_metric_percentile AS p
                  ON p.competition_id = s.competition_id
                 AND p.season_id = s.season_id
                 AND p.player_id = s.player_id
                 AND p.metric_name = m.metric_name
                 AND p.cohort_key = (CAST(s.competition_id AS TEXT) || ':' || CAST(s.season_id AS TEXT) || ':' || ?)
                WHERE {' AND '.join(clauses)}
                ORDER BY p.percentile DESC NULLS LAST, m.metric_value DESC
                LIMIT ?
            """
            params_with_suffix = [cohort_suffix, *params, int(limit)]
            rows = conn.execute(sql, params_with_suffix).fetchall()
    except FileNotFoundError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=str(exc))],
            metadata={"error": "missing_database"},
        )
    except sqlite3.DatabaseError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Season rankings cache unreadable: {exc}")],
            metadata={"error": "database_error"},
        )

    if not rows:
        return ToolResponse(
            content=[TextBlock(type="text", text="No cached season metrics match the requested player.")],
            metadata={"results": []},
        )

    player_row = rows[0]
    metrics = [
        (row["metric_name"], row["metric_value"], row["percentile"])
        for row in rows
        if row["metric_name"] and row["metric_value"] is not None
    ]
    summary = (
        f"{player_row['player_name']} · {player_row['team_name'] or 'Unknown team'} · "
        f"{player_row['competition_name'] or player_row['competition_id']} "
        f"({season_label}) — position: {player_row['position'] or 'n/a'}; minutes: {player_row['minutes']:.0f}"
    )
    bullet_text = _format_snapshot_bullets(metrics)
    return ToolResponse(
        content=[TextBlock(type="text", text=f"{summary}\n\n{bullet_text}")],
        metadata={
            "player_id": player_row["player_id"],
            "player_name": player_row["player_name"],
            "team_name": player_row["team_name"],
            "competition_id": player_row["competition_id"],
            "competition_name": player_row["competition_name"],
            "season_label": season_label,
            "metrics": [
                {"metric": metric, "value": value, "percentile": percentile}
                for metric, value, percentile in metrics
            ],
            "cohort_suffix": cohort_suffix,
        },
    )


def list_ranking_coverage_tool(
    competitions: Optional[str] = None,
    db_path: Optional[str] = None,
    limit: int = 50,
) -> ToolResponse:
    comp_ids, comp_names = _parse_competition_filters(competitions)
    try:
        with closing(_open_connection(db_path)) as conn:
            where: List[str] = []
            params: List[Any] = []
            if comp_ids:
                placeholders = ",".join("?" for _ in comp_ids)
                where.append(f"competition_id IN ({placeholders})")
                params.extend(comp_ids)
            if comp_names:
                placeholders = ",".join("?" for _ in comp_names)
                where.append(f"LOWER(competition_name) IN ({placeholders})")
                params.extend(comp_names)
            clause = f"WHERE {' AND '.join(where)}" if where else ""
            sql = f"""
                SELECT
                    competition_id,
                    COALESCE(competition_name, '') AS competition_name,
                    season_label,
                    COUNT(*) AS player_count
                FROM player_season_summary
                {clause}
                GROUP BY competition_id, competition_name, season_label
                ORDER BY season_label DESC, competition_id
                LIMIT ?
            """
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
    except FileNotFoundError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=str(exc))],
            metadata={"error": "missing_database"},
        )
    except sqlite3.DatabaseError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Season rankings cache unreadable: {exc}")],
            metadata={"error": "database_error"},
        )

    if not rows:
        return ToolResponse(
            content=[TextBlock(type="text", text="No cached season rankings found for the requested filters.")],
            metadata={"results": []},
        )
    lines = ["Cached season ranking coverage:"]
    results: List[Dict[str, Any]] = []
    for row in rows:
        line = f"- {row['competition_name'] or row['competition_id']} — {row['season_label']}: {row['player_count']} players"
        lines.append(line)
        results.append(
            {
                "competition_id": row["competition_id"],
                "competition_name": row["competition_name"],
                "season_label": row["season_label"],
                "player_count": row["player_count"],
            }
        )
    return ToolResponse(
        content=[TextBlock(type="text", text="\n".join(lines))],
        metadata={"results": results},
    )


def list_ranking_metrics_tool(
    season_label: str,
    competition_id: Optional[int] = None,
    competitions: Optional[str] = None,
    limit: int = 40,
    db_path: Optional[str] = None,
) -> ToolResponse:
    comp_ids, comp_names = _parse_competition_filters(competitions)
    if competition_id is not None:
        comp_id_int = int(competition_id)
        if comp_id_int not in comp_ids:
            comp_ids.append(comp_id_int)

    try:
        with closing(_open_connection(db_path)) as conn:
            clauses = ["s.season_label = ?"]
            params: List[Any] = [season_label]
            if comp_ids:
                placeholders = ",".join("?" for _ in comp_ids)
                clauses.append(f"s.competition_id IN ({placeholders})")
                params.extend(comp_ids)
            if comp_names:
                placeholders = ",".join("?" for _ in comp_names)
                clauses.append(f"LOWER(s.competition_name) IN ({placeholders})")
                params.extend(comp_names)
            clause = " AND ".join(clauses)
            sql = f"""
                SELECT DISTINCT m.metric_name
                  FROM player_season_metric AS m
                  JOIN player_season_summary AS s
                    ON s.competition_id = m.competition_id
                   AND s.season_id = m.season_id
                   AND s.player_id = m.player_id
                 WHERE {clause}
                 ORDER BY m.metric_name
                 LIMIT ?
            """
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
    except FileNotFoundError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=str(exc))],
            metadata={"error": "missing_database"},
        )
    except sqlite3.DatabaseError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=f"Season rankings cache unreadable: {exc}")],
            metadata={"error": "database_error"},
        )

    if not rows:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text="No ranking metrics found for the requested competition/season. Run the ingestion script first.",
                )
            ],
            metadata={"metrics": []},
        )
    metrics = [row[0] if isinstance(row, tuple) else row["metric_name"] for row in rows]
    lines = ["Available metrics:", *[f"- {metric}" for metric in metrics]]
    return ToolResponse(
        content=[TextBlock(type="text", text="\n".join(lines))],
        metadata={"metrics": metrics},
    )


def list_ranking_suites_tool() -> ToolResponse:
    suites = _load_metric_suites()
    lines = ["Available metric suites:"]
    metadata: Dict[str, Any] = {"suites": {}}
    for name, spec in sorted(suites.items()):
        metrics = spec.get("metrics") or []
        primary = spec.get("primary_metric")
        lines.append(f"- {name}: {', '.join(metrics)}")
        metadata["suites"][name] = {"metrics": metrics, "primary_metric": primary}
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=metadata)


def _resolve_suite_definition(
    suite_name: Optional[str],
    metric_names: Optional[str],
) -> tuple[List[str], Optional[str], Optional[str]]:
    metrics: List[str] = []
    primary_metric: Optional[str] = None
    requested_suite: Optional[str] = None

    if suite_name:
        suites = _load_metric_suites()
        suite = suites.get(suite_name.lower())
        if not suite:
            raise ValueError(f"Unknown suite '{suite_name}'. Call list_ranking_suites_tool first.")
        metrics.extend(suite.get("metrics", []))
        primary_metric = suite.get("primary_metric")
        requested_suite = suite_name.lower()

    if metric_names:
        provided = [part.strip() for part in metric_names.split(",") if part.strip()]
        metrics.extend(provided)

    normalised: List[str] = []
    seen: set[str] = set()
    for metric in metrics:
        normalised_metric = _normalise_metric_name(metric)
        if normalised_metric in seen:
            continue
        seen.add(normalised_metric)
        normalised.append(normalised_metric)

    if not normalised:
        raise ValueError("Provide suite_name or metrics when ranking by suite.")

    if primary_metric:
        primary_metric = _normalise_metric_name(primary_metric)
        if primary_metric not in seen:
            normalised.insert(0, primary_metric)
    else:
        primary_metric = normalised[0]

    return normalised, primary_metric, requested_suite


def _fetch_percentiles(
    conn: sqlite3.Connection,
    competition_id: int,
    season_id: int,
    player_ids: Sequence[int],
    metric_names: Sequence[str],
    cohort_suffix: str,
) -> Dict[tuple[int, str], float]:
    if not player_ids or not metric_names:
        return {}
    metric_placeholders = ",".join("?" for _ in metric_names)
    player_placeholders = ",".join("?" for _ in player_ids)
    key = f"{competition_id}:{season_id}:{cohort_suffix}" if cohort_suffix else f"{competition_id}:{season_id}:all"
    rows = conn.execute(
        f"""
        SELECT player_id, metric_name, percentile
          FROM player_metric_percentile
         WHERE competition_id = ?
           AND season_id = ?
           AND metric_name IN ({metric_placeholders})
           AND cohort_key = ?
           AND player_id IN ({player_placeholders})
        """,
        [competition_id, season_id, *metric_names, key, *player_ids],
    ).fetchall()
    return {(row[0], row[1]): float(row[2]) for row in rows if row[2] is not None}


def rank_players_by_suite_tool(
    suite_name: Optional[str] = None,
    metric_names: Optional[str] = None,
    season_label: str = "2025/2026",
    competitions: Optional[str] = None,
    limit: int = 10,
    sort_order: str = "desc",
    min_minutes: Optional[float] = None,
    position_bucket: Optional[str] = None,
    primary_metric: Optional[str] = None,
    db_path: Optional[str] = None,
) -> ToolResponse:
    try:
        resolved_metrics, default_primary, requested_suite = _resolve_suite_definition(
            suite_name, metric_names
        )
    except ValueError as exc:
        return ToolResponse(content=[TextBlock(type="text", text=str(exc))], metadata={"error": "invalid_suite"})

    if primary_metric:
        primary_metric = _normalise_metric_name(primary_metric)
    else:
        primary_metric = default_primary

    if not primary_metric or primary_metric not in resolved_metrics:
        primary_metric = resolved_metrics[0]

    order_clause = "DESC" if str(sort_order).lower() != "asc" else "ASC"
    comp_ids, comp_names = _parse_competition_filters(competitions)

    missing_metrics: List[str] = []
    try:
        with closing(_open_connection(db_path)) as conn:
            cohort_suffix = _resolve_cohort_suffix(conn, position_bucket)
            has_position_col = _column_exists(conn, "player_season_summary", "position")
            position_select = "s.position" if has_position_col else "NULL"
            primary_position_select = "s.primary_position" if _column_exists(conn, "player_season_summary", "primary_position") else "NULL"
            secondary_position_select = "s.secondary_position" if _column_exists(conn, "player_season_summary", "secondary_position") else "NULL"
            bucket_select = "s.position_bucket" if _column_exists(conn, "player_season_summary", "position_bucket") else "NULL"
            minutes_column = "s.minutes" if _column_exists(conn, "player_season_summary", "minutes") else "COALESCE(s.player_season_minutes, s.minutes_played, 0)"

            available_metrics: List[str] = []
            for metric in resolved_metrics:
                if _metric_exists(conn, metric):
                    available_metrics.append(metric)
                else:
                    missing_metrics.append(metric)

            if not available_metrics:
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text=(
                                "None of the requested metrics are present in the season cache. "
                                "Call list_ranking_metrics_tool to inspect supported metrics."
                            ),
                        )
                    ],
                    metadata={
                        "error": "missing_metrics",
                        "requested_suite": requested_suite,
                        "requested_metrics": resolved_metrics,
                    },
                )

            if missing_metrics:
                resolved_metrics = available_metrics

            select_clauses = []
            metric_params: List[Any] = []
            for metric in resolved_metrics:
                select_clauses.append(
                    f"MAX(CASE WHEN m.metric_name = ? THEN m.metric_value END) AS \"{metric}\""
                )
                metric_params.append(metric)

            where_clauses = ["s.season_label = ?"]
            where_params: List[Any] = [season_label]
            if comp_ids:
                placeholders = ",".join("?" for _ in comp_ids)
                where_clauses.append(f"s.competition_id IN ({placeholders})")
                where_params.extend(comp_ids)
            if comp_names:
                placeholders = ",".join("?" for _ in comp_names)
                where_clauses.append(f"LOWER(s.competition_name) IN ({placeholders})")
                where_params.extend(comp_names)
            if min_minutes is not None:
                where_clauses.append(f"{minutes_column} >= ?")
                where_params.append(float(min_minutes))
            if position_bucket:
                where_clauses.append("s.position_bucket = ?")
                where_params.append(position_bucket)

            metric_placeholders = ",".join("?" for _ in resolved_metrics)
            order_expression = f'"{primary_metric}" {order_clause}, {minutes_column} DESC'

            sql = f"""
                SELECT
                    s.player_id,
                    s.player_name,
                    s.team_name,
                    s.competition_id,
                    s.competition_name,
                    s.season_id,
                    s.season_label,
                    {position_select} AS position,
                    {primary_position_select} AS primary_position,
                    {secondary_position_select} AS secondary_position,
                    {bucket_select} AS position_bucket,
                    {minutes_column} AS minutes,
                    {', '.join(select_clauses)}
                FROM player_season_summary AS s
                JOIN player_season_metric AS m
                  ON m.competition_id = s.competition_id
                 AND m.season_id = s.season_id
                 AND m.player_id = s.player_id
                WHERE {' AND '.join(where_clauses)}
                  AND m.metric_name IN ({metric_placeholders})
                GROUP BY s.player_id, s.player_name, s.team_name, s.competition_id, s.competition_name, s.season_id, s.season_label
                ORDER BY {order_expression}
                LIMIT ?
            """
            params: List[Any] = [*metric_params, *where_params, *resolved_metrics, int(limit)]
            rows = conn.execute(sql, params).fetchall()

            if not rows:
                return ToolResponse(
                    content=[TextBlock(type="text", text="No cached data matches the requested suite filters.")],
                    metadata={"results": [], "metrics": resolved_metrics, "suite": requested_suite},
                )

            first_row = rows[0]
            competition_id = first_row["competition_id"]
            season_id = first_row["season_id"]
            player_ids = [row["player_id"] for row in rows]
            percentiles = _fetch_percentiles(
                conn, competition_id, season_id, player_ids, resolved_metrics, cohort_suffix
            )

    except FileNotFoundError as exc:
        return ToolResponse(content=[TextBlock(type="text", text=str(exc))], metadata={"error": "missing_database"})
    except sqlite3.DatabaseError as exc:
        return ToolResponse(content=[TextBlock(type="text", text=f"Season rankings cache unreadable: {exc}")], metadata={"error": "database_error"})

    sort_multiplier = -1 if order_clause == "DESC" else 1
    result_rows: List[Dict[str, Any]] = []
    for row in rows:
        metrics_payload: Dict[str, Dict[str, Optional[float]]] = {}
        percentile_sum = 0.0
        percentile_count = 0
        for metric in resolved_metrics:
            value = row[metric]
            pct = percentiles.get((row["player_id"], metric))
            if pct is not None:
                percentile_sum += pct
                percentile_count += 1
            metrics_payload[metric] = {"value": value, "percentile": pct}
        composite = (percentile_sum / percentile_count) if percentile_count else None
        result_rows.append(
            {
                "player_id": row["player_id"],
                "player_name": row["player_name"],
                "team_name": row["team_name"],
                "competition_id": row["competition_id"],
                "competition_name": row["competition_name"],
                "season_label": row["season_label"],
                "position": row["position"],
                "primary_position": row["primary_position"],
                "secondary_position": row["secondary_position"],
                "position_bucket": row["position_bucket"],
                "minutes": row["minutes"],
                "metrics": metrics_payload,
                "composite_percentile": composite,
            }
        )

    def _sort_key(item: Dict[str, Any]) -> tuple[float, float]:
        primary_value = item["metrics"][primary_metric]["value"]
        primary_value = float(primary_value) if primary_value is not None else 0.0
        minutes_value = float(item["minutes"] or 0.0)
        return primary_value, minutes_value

    result_rows.sort(key=_sort_key, reverse=(order_clause == "DESC"))

    header = ["#", "Player", "Team", "Comp", "Pos", "Minutes"]
    header.extend(_display_metric_name(metric) for metric in resolved_metrics)
    if any(item["composite_percentile"] is not None for item in result_rows):
        header.append("Composite %")

    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for rank, row in enumerate(result_rows[:limit], start=1):
        cells = [
            str(rank),
            row["player_name"],
            row["team_name"] or "—",
            str(row["competition_name"] or row["competition_id"]),
            row["position_bucket"] or row["position"] or "—",
            f"{row['minutes']:.0f}",
        ]
        for metric in resolved_metrics:
            payload = row["metrics"].get(metric) or {}
            value = payload.get("value")
            pct = payload.get("percentile")
            if value is None:
                cell = "—"
            else:
                cell = f"{value:.2f}"
                if pct is not None:
                    cell += f" ({pct:.1f})"
            cells.append(cell)
        if any(item["composite_percentile"] is not None for item in result_rows):
            comp = row["composite_percentile"]
            cells.append(f"{comp:.1f}" if comp is not None else "—")
        lines.append("| " + " | ".join(cells) + " |")

    return ToolResponse(
        content=[TextBlock(type="text", text="\n".join(lines))],
        metadata={
            "suite": requested_suite,
            "metrics": resolved_metrics,
            "primary_metric": primary_metric,
            "results": result_rows,
            "missing_metrics": missing_metrics,
        },
    )


def register_ranking_tools(
    toolkit: Optional[Toolkit] = None,
    *,
    group_name: str = "season-rankings",
    activate: bool = True,
) -> Toolkit:
    """
    Register ranking tools with the provided toolkit.
    """
    toolkit = toolkit or Toolkit()
    if not hasattr(toolkit, "create_tool_group"):
        if hasattr(toolkit, "register_tool_function"):
            toolkit.register_tool_function(rank_players_by_metric_tool, group_name=group_name)
            toolkit.register_tool_function(player_percentile_snapshot_tool, group_name=group_name)
            return toolkit
        raise AttributeError("Provided toolkit does not expose create_tool_group or register_tool_function.")

    try:
        toolkit.create_tool_group(
            group_name,
            description="Cached season ranking helpers (leaderboards, percentiles).",
            active=activate,
        )
    except ValueError:
        if hasattr(toolkit, "update_tool_groups"):
            toolkit.update_tool_groups([group_name], activate)

    toolkit.register_tool_function(
        rank_players_by_metric_tool,
        group_name=group_name,
        func_description="Return a cached leaderboard for a metric/season combination.",
    )
    toolkit.register_tool_function(
        player_percentile_snapshot_tool,
        group_name=group_name,
        func_description="Summarise cached metrics and percentiles for a specific player.",
    )
    toolkit.register_tool_function(
        list_ranking_coverage_tool,
        group_name=group_name,
        func_description="List competitions and seasons currently cached in the season rankings database.",
    )
    toolkit.register_tool_function(
        list_ranking_metrics_tool,
        group_name=group_name,
        func_description="List available metric columns for the cached season rankings.",
    )
    toolkit.register_tool_function(
        list_ranking_suites_tool,
        group_name=group_name,
        func_description="List available metric suites for bundled leaderboards.",
    )
    toolkit.register_tool_function(
        rank_players_by_suite_tool,
        group_name=group_name,
        func_description="Rank players across a suite of metrics (passing, shooting, pressing, etc.).",
    )
    return toolkit
