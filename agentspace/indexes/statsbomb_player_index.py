"""Local player index built from StatsBomb season aggregates.

This module builds and queries a lightweight player index to speed up
player/team resolution. It now reuses the canonicalization logic from
``agentspace.services.statsbomb_tools`` so names with diacritics (Nordic,
Turkish, Central/Eastern European, etc.) normalise consistently.
In addition to exact key lookup, ``query_player_index`` performs a small
fuzzy fallback to catch near-matches (diacritics/spacing variants).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..clients.statsbomb import StatsBombClient
from ..services.statsbomb_tools import _canonical as _sb_canonical

TOP_COMPETITION_IDS = (
    2,
    11,
    9,
    12,
    7,
    6,
    46,
    13,
    37,
    16,
    35,
    353,
    69,
    87,
    66,
    86,
    165,
)


def _canonical(value: str) -> str:
    """Delegate to the shared canonicaliser for consistent matching.

    This normalises diacritics (e.g., ö→o, æ→ae, ı→i, ß→ss), collapses
    whitespace, lowercases, and strips punctuation where appropriate.
    """
    return _sb_canonical(value)

INDEX_VERSION = 1


@dataclass
class PlayerIndexConfig:
    competitions: Iterable[int] = tuple(TOP_COMPETITION_IDS)
    season_label: str = "2025/2026"
    min_minutes: float = 0.0
    index_path: Path = Path(".cache/player_index.json")


def _season_id_for_label(competition_id: int, season_label: str, *, use_cache: bool = True) -> Optional[int]:
    client = StatsBombClient()
    # StatsBomb v4 competitions endpoint includes season ids in list_matches metadata.
    comps = client.list_competitions(use_cache=use_cache)
    canonical_label = season_label.replace("-", "/")
    for comp in comps:
        if comp.get("competition_id") != competition_id:
            continue
        if _canonical(str(comp.get("season_name", ""))) == _canonical(canonical_label):
            return comp.get("season_id")
    return None


def _fetch_player_season_stats(competition_id: int, season_id: int, *, use_cache: bool = True) -> List[Dict[str, object]]:
    client = StatsBombClient()
    try:
        rows = client.get_player_season_stats(competition_id, season_id, use_cache=use_cache)
        if not rows:
            return []
        return list(rows)
    except Exception:  # pragma: no cover - API failures fallback to empty
        return []


def build_player_index(config: PlayerIndexConfig) -> Dict[str, List[Dict[str, object]]]:
    index: Dict[str, List[Dict[str, object]]] = {}
    for comp_id in config.competitions:
        season_id = _season_id_for_label(comp_id, config.season_label, use_cache=True)
        if season_id is None:
            continue
        rows = _fetch_player_season_stats(comp_id, season_id)
        for row in rows:
            canonical_name = _canonical(str(row.get("player_name", "")))
            if not canonical_name:
                continue
            minutes = float(row.get("player_season_minutes") or 0.0)
            if minutes < float(config.min_minutes):
                continue
            enriched = dict(row)
            enriched.update(
                {
                    "competition_id": comp_id,
                    "season_label": config.season_label,
                }
            )
            index.setdefault(canonical_name, []).append(enriched)
    return index


def _load_index(path: Path) -> Optional[Dict[str, List[Dict[str, object]]]]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict) and "index" in data:
                data = data.get("index", {})
            if not isinstance(data, dict):
                return None
            result: Dict[str, List[Dict[str, object]]] = {}
            for key, value in data.items():
                if isinstance(value, list):
                    result[str(key)] = [dict(item) for item in value if isinstance(item, dict)]
            return result
    except (json.JSONDecodeError, OSError):
        return None


def _save_index(path: Path, data: Dict[str, List[Dict[str, object]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": INDEX_VERSION,
        "index": data,
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)


def refresh_player_index(config: Optional[PlayerIndexConfig] = None) -> Dict[str, List[Dict[str, object]]]:
    config = config or PlayerIndexConfig()
    index = build_player_index(config)
    _save_index(config.index_path, index)
    return index


def get_player_index(config: Optional[PlayerIndexConfig] = None) -> Dict[str, List[Dict[str, object]]]:
    config = config or PlayerIndexConfig()
    cached = _load_index(config.index_path)
    if cached is not None:
        return cached
    return refresh_player_index(config)


def query_player_index(name: str, *, config: Optional[PlayerIndexConfig] = None) -> List[Dict[str, object]]:
    canonical_name = _canonical(name)
    if not canonical_name:
        return []
    index = get_player_index(config)
    # Exact hit first
    rows = index.get(canonical_name, [])
    if rows:
        return rows

    # Fuzzy fallback: try near-matches on the index keys.
    # This is a lightweight pass suitable for the small on-disk index.
    best_key = None
    best_score = 0.0
    for key in index.keys():
        # quick token overlap boost
        tokens_a = set(canonical_name.split())
        tokens_b = set(str(key).split())
        token_overlap = 1.0 if (tokens_a & tokens_b) else 0.0
        # sequence similarity ignoring spaces
        a = canonical_name.replace(" ", "")
        b = str(key).replace(" ", "")
        sim = SequenceMatcher(a=a, b=b).ratio()
        score = sim + 0.25 * token_overlap
        if score > best_score:
            best_score = score
            best_key = key

    # Threshold tuned to catch diacritic/spelling variants without overmatching
    if best_key is not None and best_score >= 0.85:
        return index.get(best_key, [])
    return []
