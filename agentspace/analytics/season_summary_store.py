"""
Season summary ingestion and storage helpers for player ranking workflows.
"""

from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from bisect import bisect_right
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from agentspace.exceptions import APINotFoundError
from agentspace.services.statsbomb_tools import (
    fetch_player_season_stats_data,
    season_id_for_label,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(".cache/season_summaries.db")
DEFAULT_CONFIG_PATH = Path("config/season_tracking.yml")


# ---------------------------------------------------------------------------
# Configuration models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PositionBucketConfig:
    name: str
    include: Tuple[str, ...] = ()


@dataclass(frozen=True)
class SeasonConfig:
    label: str
    min_minutes: Optional[float] = None
    min_minutes_percent: Optional[float] = None
    min_minutes_floor: Optional[float] = None
    season_id: Optional[int] = None
    percentile_positions: Tuple[PositionBucketConfig, ...] = ()


@dataclass(frozen=True)
class CompetitionConfig:
    name: Optional[str]
    competition_id: Optional[int]
    seasons: Tuple[SeasonConfig, ...] = ()


@dataclass(frozen=True)
class SeasonTrackingConfig:
    tracked_competitions: Tuple[CompetitionConfig, ...] = ()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def resolve_db_path(db_path: Optional[Path] = None) -> Path:
    """
    Resolve the SQLite database path using the provided override or environment variable.
    """
    if db_path is not None:
        return db_path
    override = os.getenv("AGENTSPACE_SEASON_DB")
    if override:
        return Path(override)
    return DEFAULT_DB_PATH


def resolve_config_path(config_path: Optional[Path] = None) -> Path:
    """
    Resolve the season tracking config path using env overrides when present.
    """
    if config_path is not None:
        return config_path
    override = os.getenv("AGENTSPACE_SEASON_CONFIG")
    if override:
        return Path(override)
    return DEFAULT_CONFIG_PATH


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Season tracking config not found at {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_season_tracking_config(path: Optional[Path] = None) -> SeasonTrackingConfig:
    """
    Parse the season tracking configuration file into dataclasses.
    """
    config_path = resolve_config_path(path)
    raw = _load_yaml(config_path)
    competitions: List[CompetitionConfig] = []
    for item in raw.get("tracked_competitions", []) or []:
        name = item.get("name")
        competition_id = item.get("competition_id")
        seasons_cfg: List[SeasonConfig] = []
        for season in item.get("seasons", []) or []:
            percentile_buckets = tuple(
                PositionBucketConfig(
                    name=bucket.get("name", ""),
                    include=tuple(bucket.get("include", []) or []),
                )
                for bucket in season.get("percentile_positions", []) or []
                if bucket.get("name")
            )

            min_minutes_value = season.get("min_minutes")
            min_minutes: Optional[float]
            min_percent = season.get("min_minutes_percent")
            min_floor = season.get("min_minutes_floor")

            if isinstance(min_minutes_value, str):
                stripped = min_minutes_value.strip()
                if stripped.endswith("%"):
                    try:
                        min_percent = float(stripped[:-1]) / 100.0
                        min_minutes = None
                    except ValueError:
                        min_minutes = None
                else:
                    try:
                        min_minutes = float(stripped)
                    except ValueError:
                        min_minutes = None
            else:
                min_minutes = min_minutes_value if min_minutes_value is None else float(min_minutes_value)

            if isinstance(min_percent, str):
                try:
                    min_percent = float(min_percent)
                except ValueError:
                    min_percent = None
            if isinstance(min_floor, str):
                try:
                    min_floor = float(min_floor)
                except ValueError:
                    min_floor = None

            seasons_cfg.append(
                SeasonConfig(
                    label=str(season.get("label", "")).strip(),
                    min_minutes=min_minutes,
                    min_minutes_percent=min_percent,
                    min_minutes_floor=min_floor,
                    season_id=season.get("season_id"),
                    percentile_positions=percentile_buckets,
                )
            )
        competitions.append(
            CompetitionConfig(
                name=name,
                competition_id=competition_id,
                seasons=tuple(seasons_cfg),
            )
        )
    return SeasonTrackingConfig(tracked_competitions=tuple(competitions))


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalise_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    try:
        result = float(value)
    except (TypeError, ValueError):
        try:
            result = float(str(value))
        except (TypeError, ValueError):
            return None
    if math.isnan(result) or math.isinf(result):
        return None
    return float(result)


def _player_identifier(record: Dict[str, Any]) -> Optional[int]:
    for key in ("player_id", "playerId", "id"):
        candidate = record.get(key)
        if candidate is not None:
            try:
                return int(candidate)
            except (TypeError, ValueError):
                continue
    name = record.get("player_name")
    if not name:
        return None
    team = record.get("team_name") or ""
    payload = f"{name}|{team}".encode("utf-8")
    return int(zlib.crc32(payload))


def _extract_metrics(record: Dict[str, Any]) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    for key, value in record.items():
        if key in {
            "competition_id",
            "season_id",
            "season_label",
            "competition_name",
            "player_id",
            "player_name",
            "team_id",
            "team_name",
            "position",
            "minutes",
            "player_season_minutes",
            "minutes_played",
        }:
            continue
        numeric_val = _normalise_numeric(value)
        if numeric_val is None:
            continue
        metrics[key] = numeric_val
    return metrics


@dataclass
class PlayerSeasonEntry:
    competition_id: int
    competition_name: Optional[str]
    season_id: int
    season_label: str
    player_id: int
    player_name: str
    team_id: Optional[int]
    team_name: Optional[str]
    position: Optional[str]
    primary_position: Optional[str]
    secondary_position: Optional[str]
    position_bucket: Optional[str]
    minutes: float
    metrics: Dict[str, float]
    metadata_json: str


def _compute_percentiles(values: Sequence[float]) -> List[float]:
    if not values:
        return []
    if len(values) == 1:
        return [100.0]
    sorted_values = sorted(float(v) for v in values)
    total = float(len(sorted_values))
    percentiles: List[float] = []
    for value in values:
        index = float(bisect_right(sorted_values, float(value)))
        percentiles.append((index / total) * 100.0)
    return percentiles


# ---------------------------------------------------------------------------
# Storage layer
# ---------------------------------------------------------------------------


class SeasonSummaryStore:
    """
    Manage the season summaries SQLite cache.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def ensure_schema(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS player_season_summary (
                competition_id INTEGER NOT NULL,
                season_id INTEGER NOT NULL,
                season_label TEXT,
                player_id INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                team_id INTEGER,
                team_name TEXT,
                position TEXT,
                minutes REAL,
                competition_name TEXT,
                metadata_json TEXT,
                last_updated TEXT NOT NULL,
                PRIMARY KEY (competition_id, season_id, player_id)
            );

            CREATE TABLE IF NOT EXISTS player_season_metric (
                competition_id INTEGER NOT NULL,
                season_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (competition_id, season_id, player_id, metric_name)
            );

            CREATE TABLE IF NOT EXISTS player_metric_percentile (
                competition_id INTEGER NOT NULL,
                season_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                cohort_key TEXT NOT NULL,
                percentile REAL NOT NULL,
                metric_value REAL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (competition_id, season_id, player_id, metric_name, cohort_key)
            );

            CREATE TABLE IF NOT EXISTS ingestion_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                config_path TEXT,
                details TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_player_summary_season
                ON player_season_summary (competition_id, season_id);
            CREATE INDEX IF NOT EXISTS idx_player_metric_name
                ON player_season_metric (metric_name);
            CREATE INDEX IF NOT EXISTS idx_percentile_metric
                ON player_metric_percentile (metric_name, cohort_key);
            """
        )
        SeasonSummaryStore._ensure_column(conn, "player_season_summary", "position", "TEXT")
        SeasonSummaryStore._ensure_column(conn, "player_season_summary", "competition_name", "TEXT")
        SeasonSummaryStore._ensure_column(conn, "player_season_summary", "minutes", "REAL")
        SeasonSummaryStore._ensure_column(conn, "player_season_summary", "metadata_json", "TEXT")
        SeasonSummaryStore._ensure_column(conn, "player_season_summary", "primary_position", "TEXT")
        SeasonSummaryStore._ensure_column(conn, "player_season_summary", "secondary_position", "TEXT")
        SeasonSummaryStore._ensure_column(conn, "player_season_summary", "position_bucket", "TEXT")
        SeasonSummaryStore._ensure_column(conn, "ingestion_runs", "config_path", "TEXT")
        SeasonSummaryStore._ensure_column(conn, "ingestion_runs", "details", "TEXT")
        # Metric tables evolved; ensure required columns exist for legacy caches.
        for column, definition in (
            ("competition_id", "INTEGER"),
            ("season_id", "INTEGER"),
            ("player_id", "INTEGER"),
            ("metric_name", "TEXT"),
            ("metric_value", "REAL"),
            ("updated_at", "TEXT"),
        ):
            SeasonSummaryStore._ensure_column(conn, "player_season_metric", column, definition)
        for column, definition in (
            ("competition_id", "INTEGER"),
            ("season_id", "INTEGER"),
            ("player_id", "INTEGER"),
            ("metric_name", "TEXT"),
            ("cohort_key", "TEXT"),
            ("percentile", "REAL"),
            ("metric_value", "REAL"),
            ("updated_at", "TEXT"),
        ):
            SeasonSummaryStore._ensure_column(conn, "player_metric_percentile", column, definition)

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        if column in existing:
            return
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        except sqlite3.DatabaseError as exc:  # pragma: no cover - best effort migration
            LOGGER.warning("Failed adding column %s to %s: %s", column, table, exc)

    def begin_ingestion_run(
        self,
        conn: sqlite3.Connection,
        *,
        started_at: Optional[str] = None,
        config_path: Optional[str] = None,
        status: str = "running",
        details: Optional[str] = None,
    ) -> int:
        ts = started_at or _utcnow_iso()
        cursor = conn.execute(
            """
            INSERT INTO ingestion_runs (started_at, status, config_path, details)
            VALUES (?, ?, ?, ?)
            """,
            (ts, status, config_path, details),
        )
        return int(cursor.lastrowid)

    def complete_ingestion_run(
        self,
        conn: sqlite3.Connection,
        run_id: int,
        *,
        status: str,
        details: Optional[str] = None,
    ) -> None:
        conn.execute(
            """
            UPDATE ingestion_runs
               SET completed_at = ?, status = ?, details = COALESCE(?, details)
             WHERE run_id = ?
            """,
            (_utcnow_iso(), status, details, run_id),
        )

    def upsert_player_entry(
        self,
        conn: sqlite3.Connection,
        entry: PlayerSeasonEntry,
        *,
        timestamp: Optional[str] = None,
    ) -> None:
        updated_at = timestamp or _utcnow_iso()
        conn.execute(
            """
            INSERT INTO player_season_summary (
                competition_id,
                season_id,
                season_label,
                player_id,
                player_name,
                team_id,
                team_name,
                position,
                primary_position,
                secondary_position,
                position_bucket,
                minutes,
                competition_name,
                metadata_json,
                last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(competition_id, season_id, player_id)
            DO UPDATE SET
                season_label=excluded.season_label,
                player_name=excluded.player_name,
                team_id=excluded.team_id,
                team_name=excluded.team_name,
                position=excluded.position,
                primary_position=excluded.primary_position,
                secondary_position=excluded.secondary_position,
                position_bucket=excluded.position_bucket,
                minutes=excluded.minutes,
                competition_name=excluded.competition_name,
                metadata_json=excluded.metadata_json,
                last_updated=excluded.last_updated
            """,
            (
                entry.competition_id,
                entry.season_id,
                entry.season_label,
                entry.player_id,
                entry.player_name,
                entry.team_id,
                entry.team_name,
                entry.position,
                 entry.primary_position,
                 entry.secondary_position,
                 entry.position_bucket,
                entry.minutes,
                entry.competition_name,
                entry.metadata_json,
                updated_at,
            ),
        )
        for metric_name, metric_value in entry.metrics.items():
            conn.execute(
                """
                INSERT INTO player_season_metric (
                    competition_id,
                    season_id,
                    player_id,
                    metric_name,
                    metric_value,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(competition_id, season_id, player_id, metric_name)
                DO UPDATE SET
                    metric_value=excluded.metric_value,
                    updated_at=excluded.updated_at
                """,
                (
                    entry.competition_id,
                    entry.season_id,
                    entry.player_id,
                    metric_name,
                    metric_value,
                    updated_at,
                ),
            )

    def replace_percentiles(
        self,
        conn: sqlite3.Connection,
        competition_id: int,
        season_id: int,
        percentile_rows: Iterable[Tuple[int, str, str, float, float]],
        *,
        timestamp: Optional[str] = None,
    ) -> None:
        updated_at = timestamp or _utcnow_iso()
        conn.execute(
            """
            DELETE FROM player_metric_percentile
             WHERE competition_id = ? AND season_id = ?
            """,
            (competition_id, season_id),
        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO player_metric_percentile (
                competition_id,
                season_id,
                player_id,
                metric_name,
                cohort_key,
                percentile,
                metric_value,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    competition_id,
                    season_id,
                    player_id,
                    metric_name,
                    cohort_key,
                    percentile,
                    metric_value,
                    updated_at,
                )
                for player_id, metric_name, cohort_key, percentile, metric_value in percentile_rows
            ),
        )


# ---------------------------------------------------------------------------
# Ingestion orchestration
# ---------------------------------------------------------------------------


def _build_player_entry(
    record: Dict[str, Any],
    *,
    competition_id: int,
    competition_name: Optional[str],
    season_id: int,
    season_label: str,
) -> Optional[PlayerSeasonEntry]:
    player_id = _player_identifier(record)
    if player_id is None:
        LOGGER.warning(
            "Skipping player with missing identifier in competition=%s season=%s: %s",
            competition_id,
            season_id,
            record.get("player_name"),
        )
        return None

    minutes = (
        _normalise_numeric(
            record.get("player_season_minutes") or record.get("minutes_played")
        )
        or 0.0
    )
    primary_position = record.get("primary_position") or record.get("player_position") or record.get("position")
    secondary_position = record.get("secondary_position")
    position_bucket = _position_bucket(primary_position)

    entry = PlayerSeasonEntry(
        competition_id=competition_id,
        competition_name=competition_name,
        season_id=season_id,
        season_label=season_label,
        player_id=player_id,
        player_name=str(record.get("player_name") or ""),
        team_id=record.get("team_id"),
        team_name=record.get("team_name"),
        position=record.get("position") or record.get("player_position") or primary_position,
        primary_position=primary_position,
        secondary_position=secondary_position,
        position_bucket=position_bucket,
        minutes=minutes,
        metrics=_extract_metrics(record),
        metadata_json=json.dumps(record, ensure_ascii=False, sort_keys=True),
    )
    return entry


def _cohort_key(
    competition_id: int,
    season_id: int,
    suffix: str,
) -> str:
    return f"{competition_id}:{season_id}:{suffix}"


def _build_cohorts(
    entries: Sequence[PlayerSeasonEntry],
    season_config: SeasonConfig,
    *,
    competition_id: int,
    season_id: int,
) -> Dict[str, List[PlayerSeasonEntry]]:
    cohorts: Dict[str, List[PlayerSeasonEntry]] = {
        _cohort_key(competition_id, season_id, "all"): list(entries)
    }
    for bucket in season_config.percentile_positions:
        include_set = {name.casefold() for name in bucket.include}
        if not include_set:
            continue
        filtered = [
            entry
            for entry in entries
            if entry.position and entry.position.casefold() in include_set
        ]
        cohorts[_cohort_key(competition_id, season_id, f"position:{bucket.name}")] = filtered
    return cohorts


def _gather_metric_names(entries: Sequence[PlayerSeasonEntry]) -> List[str]:
    names: set[str] = set()
    for entry in entries:
        names.update(entry.metrics.keys())
    return sorted(names)


def _compute_percentile_rows(
    entries: Sequence[PlayerSeasonEntry],
    cohorts: Dict[str, List[PlayerSeasonEntry]],
) -> List[Tuple[int, str, str, float, float]]:
    metric_names = _gather_metric_names(entries)
    rows: List[Tuple[int, str, str, float, float]] = []
    for cohort_key, cohort_entries in cohorts.items():
        filtered = [entry for entry in cohort_entries if entry.metrics]
        if not filtered:
            continue
        for metric_name in metric_names:
            values: List[float] = []
            players: List[PlayerSeasonEntry] = []
            for entry in filtered:
                value = entry.metrics.get(metric_name)
                if value is None:
                    continue
                values.append(value)
                players.append(entry)
            if not values:
                continue
            percentile_scores = _compute_percentiles(values)
            for entry, percentile, metric_value in zip(players, percentile_scores, values):
                rows.append(
                    (
                        entry.player_id,
                        metric_name,
                        cohort_key,
                        float(percentile),
                        float(metric_value),
                    )
                )
    return rows


def ingest_competition_season(
    store: SeasonSummaryStore,
    conn: sqlite3.Connection,
    competition: CompetitionConfig,
    season: SeasonConfig,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    label = season.label
    if not label:
        raise ValueError("Season label is required in the tracking configuration.")
    if competition.competition_id is None:
        raise ValueError(f"Competition '{competition.name}' must define competition_id.")
    season_id = season.season_id
    if season_id is None:
        season_id = season_id_for_label(
            competition.competition_id,
            label,
            use_cache=True,
        )
    if season_id is None:
        raise ValueError(
            f"Unable to resolve season_id for competition={competition.competition_id} label={label}"
        )

    LOGGER.info(
        "Fetching player season stats for competition=%s season_id=%s (%s)",
        competition.competition_id,
        season_id,
        label,
    )
    try:
        raw_rows = fetch_player_season_stats_data(
            competition.competition_id,
            season_id,
            min_minutes=None,
            use_cache=True,
        )
    except APINotFoundError as exc:
        LOGGER.warning(
            "StatsBomb API returned not found for competition=%s season_id=%s: %s",
            competition.competition_id,
            season_id,
            exc,
        )
        raw_rows = []

    base_threshold = float(season.min_minutes or 0.0)
    dynamic_threshold = 0.0
    if raw_rows and season.min_minutes_percent:
        minutes_values = [
            _normalise_numeric(row.get("player_season_minutes") or row.get("minutes_played"))
            for row in raw_rows
        ]
        max_minutes = max(minutes_values) if minutes_values else 0.0
        dynamic_threshold = max_minutes * float(season.min_minutes_percent)

    threshold_candidates: list[tuple[str, float]] = []
    if dynamic_threshold > 0:
        threshold_candidates.append(("dynamic", dynamic_threshold))
    if base_threshold > 0 and (not threshold_candidates or base_threshold != threshold_candidates[0][1]):
        threshold_candidates.append(("base", base_threshold))
    if season.min_minutes_floor is not None:
        floor_value = float(season.min_minutes_floor)
        if floor_value > 0:
            threshold_candidates.append(("floor", floor_value))

    def _apply_threshold(rows_source: List[Dict[str, Any]], limit: float) -> List[Dict[str, Any]]:
        if limit <= 0:
            return list(rows_source)
        return [
            row
            for row in rows_source
            if _normalise_numeric(row.get("player_season_minutes") or row.get("minutes_played")) >= limit
        ]

    rows = list(raw_rows)
    for name, limit in threshold_candidates:
        filtered = _apply_threshold(raw_rows, limit)
        if filtered:
            rows = filtered
            break
    if not rows:
        rows = raw_rows

    entries: List[PlayerSeasonEntry] = []
    for record in rows:
        entry = _build_player_entry(
            record,
            competition_id=competition.competition_id,
            competition_name=competition.name,
            season_id=season_id,
            season_label=label,
        )
        if not entry:
            continue
        entries.append(entry)

    timestamp = _utcnow_iso()
    if not dry_run:
        for entry in entries:
            store.upsert_player_entry(conn, entry, timestamp=timestamp)
        cohorts = _build_cohorts(
            entries,
            season,
            competition_id=competition.competition_id,
            season_id=season_id,
        )
        percentile_rows = _compute_percentile_rows(entries, cohorts)
        store.replace_percentiles(
            conn,
            competition.competition_id,
            season_id,
            percentile_rows,
            timestamp=timestamp,
        )

    processed = len(entries)
    LOGGER.info(
        "Processed %s player records for competition=%s season_id=%s",
        processed,
        competition.competition_id,
        season_id,
    )
    return {
        "competition_id": competition.competition_id,
        "competition_name": competition.name,
        "season_id": season_id,
        "season_label": label,
        "processed_players": processed,
        "dry_run": dry_run,
    }


def ingest_from_config(
    store: SeasonSummaryStore,
    config: SeasonTrackingConfig,
    *,
    competition_filters: Optional[Sequence[str]] = None,
    config_path: Optional[Path] = None,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    filters = {f.lower() for f in (competition_filters or [])}
    results: List[Dict[str, Any]] = []
    with store.connect() as conn:
        if not dry_run:
            store.ensure_schema(conn)
        run_id: Optional[int] = None
        if not dry_run:
            run_id = store.begin_ingestion_run(
                conn,
                started_at=_utcnow_iso(),
                config_path=str(config_path) if config_path else None,
                status="running",
            )
        try:
            for competition in config.tracked_competitions:
                if filters:
                    token = str(competition.competition_id or "").lower()
                    name = (competition.name or "").lower()
                    if not any(
                        matcher in {token, name} or matcher == name
                        for matcher in filters
                    ):
                        continue
                for season in competition.seasons:
                    result = ingest_competition_season(
                        store,
                        conn,
                        competition,
                        season,
                        dry_run=dry_run,
                    )
                    results.append(result)
            if not dry_run and run_id is not None:
                store.complete_ingestion_run(conn, run_id, status="success")
        except Exception as exc:  # pragma: no cover - propagate after logging run failure
            if not dry_run and run_id is not None:
                store.complete_ingestion_run(
                    conn,
                    run_id,
                    status="failed",
                    details=str(exc),
                )
            raise
    return results
POSITION_BUCKET_MAP = {
    "goalkeeper": "GK",
    "keeper": "GK",
    "centre back": "CB",
    "center back": "CB",
    "central defender": "CB",
    "full back": "FB",
    "left back": "FB",
    "right back": "FB",
    "wing back": "WB",
    "wing-back": "WB",
    "defensive midfielder": "DM",
    "holding midfielder": "DM",
    "anchor": "DM",
    "central midfielder": "CM",
    "centre midfielder": "CM",
    "attacking midfielder": "AM",
    "second striker": "AM",
    "winger": "W",
    "wide forward": "W",
    "left wing": "W",
    "right wing": "W",
    "forward": "ST",
    "striker": "ST",
    "centre forward": "ST",
    "central forward": "ST",
}


def _position_bucket(primary: Optional[str]) -> Optional[str]:
    if not primary:
        return None
    key = primary.lower()
    for needle, bucket in POSITION_BUCKET_MAP.items():
        if needle in key:
            return bucket
    return None
