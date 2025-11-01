#!/usr/bin/env python
"""
CLI entrypoint to ingest player season summaries into the SQLite cache.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List

from agentspace.analytics.season_summary_store import (
    SeasonSummaryStore,
    ingest_from_config,
    load_season_tracking_config,
    resolve_config_path,
    resolve_db_path,
)


LOGGER = logging.getLogger(__name__)


def _parse_competition_filters(values: List[str] | None) -> List[str]:
    if not values:
        return []
    filters: List[str] = []
    for value in values:
        for token in value.split(","):
            token = token.strip()
            if token:
                filters.append(token)
    return filters


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest StatsBomb player season summaries into a SQLite cache.",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to season tracking configuration (defaults to AGENTSPACE_SEASON_CONFIG or config/season_tracking.yml).",
    )
    parser.add_argument(
        "--database",
        type=str,
        help="Path to the target SQLite database (defaults to AGENTSPACE_SEASON_DB or .cache/season_summaries.db).",
    )
    parser.add_argument(
        "--competition",
        "-c",
        action="append",
        help="Limit ingestion to specific competitions (name or id). Supports multiple values or comma separated list.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute without writing to the database.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    level = getattr(logging, str(args.log_level).upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config_path = resolve_config_path(Path(args.config) if args.config else None)
    db_path = resolve_db_path(Path(args.database) if args.database else None)

    LOGGER.info("Loading season tracking config from %s", config_path)
    config = load_season_tracking_config(config_path)
    store = SeasonSummaryStore(db_path)

    filters = _parse_competition_filters(args.competition)
    if args.dry_run:
        LOGGER.info("Running in dry-run mode; no database writes will be performed.")
    try:
        results = ingest_from_config(
            store,
            config,
            competition_filters=filters,
            config_path=config_path,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        LOGGER.error("Season summaries ingestion failed: %s", exc, exc_info=level <= logging.DEBUG)
        return 1

    processed = sum(item.get("processed_players", 0) for item in results)
    LOGGER.info(
        "Ingestion completed (%s). Processed %s players across %s season slices.",
        "dry-run" if args.dry_run else "written",
        processed,
        len(results),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

