"""
Agentscope toolkit: Offline StatsBomb index lookups (no live API calls).

Uses prebuilt JSON indices from `.cache/db_index/` produced by
`agentspace.indexes.statsbomb_db_index` for near-instant lookup.
"""
import json
import difflib
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agentscope.message import TextBlock
from agentscope.tool import Toolkit, ToolResponse

from ..clients.statsbomb import StatsBombClient

DEFAULT_INDEX_DIR = Path(".cache/db_index")


@dataclass
class _IndexStore:
    root: Path = DEFAULT_INDEX_DIR
    competitions: Dict[str, Any] | None = None
    seasons: Dict[str, Any] | None = None
    teams: Dict[str, Any] | None = None
    players: Dict[str, Any] | None = None
    managers: Dict[str, Any] | None = None
    matches: Dict[str, Any] | None = None
    relationships: Dict[str, Any] | None = None
    stats: Dict[str, Any] | None = None
    validation: Dict[str, Any] | None = None

    def _load_json(self, name: str) -> Dict[str, Any]:
        p = self.root / name
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)

    def ensure_loaded(self) -> None:
        if self.competitions is not None:
            return
        self.competitions = self._load_json("competitions_index.json")
        self.seasons = self._load_json("seasons_index.json")
        self.teams = self._load_json("teams_index.json")
        self.players = self._load_json("players_index.json")
        # Some indexes may not exist depending on build options; guard reads
        try:
            self.managers = self._load_json("managers_index.json")
        except FileNotFoundError:
            self.managers = {"by_id": {}, "by_name": {}}
        self.matches = self._load_json("matches_index.json")
        self.relationships = self._load_json("relationship_graph.json")
        try:
            self.stats = self._load_json("stats_summary.json")
        except FileNotFoundError:
            self.stats = {}
        try:
            self.validation = self._load_json("validation_report.json")
        except FileNotFoundError:
            self.validation = {}


_STORE = _IndexStore()


def _err(text: str, meta: Dict[str, Any]) -> ToolResponse:
    return ToolResponse(content=[TextBlock(type="text", text=text)], metadata=meta)


def _best_name_id(by_name: Dict[str, Any], query: str) -> Optional[int]:
    # Try direct, lowercase, then difflib fuzzy
    direct = by_name.get(query) or by_name.get(query.lower())
    if isinstance(direct, int):
        return direct
    # Convert values to int keys if strings
    direct2 = by_name.get(query) or by_name.get(query.lower())
    if isinstance(direct2, str) and direct2.isdigit():
        return int(direct2)
    # Fuzzy
    keys = list(by_name.keys())
    candidates = difflib.get_close_matches(query.lower(), [k.lower() for k in keys], n=5, cutoff=0.7)
    for cand in candidates:
        # map candidate back to original case key
        for k in keys:
            if k.lower() == cand:
                v = by_name.get(k)
                if isinstance(v, int):
                    return v
                if isinstance(v, str) and v.isdigit():
                    return int(v)
    return None


def _canonical_name(text: Optional[str]) -> str:
    if not text:
        return ""
    normalised = unicodedata.normalize("NFKD", text)
    stripped = normalised.encode("ascii", "ignore").decode("ascii")
    return "".join(stripped.lower().split())


def _fallback_player_mapping(
    name: str,
    *,
    team_id: Optional[int] = None,
    season_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fallback resolver that queries the live StatsBomb player mapping API when
    the offline index cannot find a player. Provides a light fuzzy match using
    canonical forms.
    """

    client = StatsBombClient()
    rows = client.get_player_mapping(
        season_id=season_id,
        all_account_data=True,
        add_matches_played=False,
        use_cache=True,
    )
    if not rows:
        return []

    target = _canonical_name(name)
    candidates: List[Tuple[float, Dict[str, Any]]] = []
    for row in rows:
        player_name = row.get("player_name")
        if not player_name:
            continue
        if team_id is not None and row.get("offline_team_id") != team_id:
            continue
        candidate = _canonical_name(player_name)
        if not candidate:
            continue

        score = difflib.SequenceMatcher(a=target, b=candidate).ratio()
        if target in candidate or candidate in target:
            score = max(score, 0.95)
        if score < 0.80:
            continue
        candidates.append(
            (
                score,
                {
                    "player_id": row.get("offline_player_id"),
                    "player_name": player_name,
                    "name": player_name,
                    "team_id": row.get("offline_team_id"),
                    "team_name": row.get("team_name"),
                    "season_id": row.get("season_id"),
                    "source": "statsbomb-player-mapping",
                },
            )
        )

    if not candidates:
        return []

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in candidates[:10]]


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def index_status() -> ToolResponse:
    try:
        _STORE.ensure_loaded()
    except FileNotFoundError:
        return _err(
            "Index files missing. Build with `python -m agentspace.indexes.statsbomb_db_index`.",
            {"index_dir": str(_STORE.root)},
        )
    counts = (_STORE.stats or {}).get("counts") or {}
    generated = (_STORE.stats or {}).get("generated_at")
    lines = [
        f"Index generated at: {generated or 'unknown'}",
        f"Entities – competitions: {counts.get('competitions', 'n/a')}, seasons: {counts.get('seasons', 'n/a')}, teams: {counts.get('teams', 'n/a')}, players: {counts.get('players', 'n/a')}, matches: {counts.get('matches', 'n/a')}.",
        "Validation issues: " + str(((_STORE.validation or {}).get("issues") or [] )[:3]) + (" ..." if ((_STORE.validation or {}).get("issues") or [] ) else ""),
    ]
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata={"stats": _STORE.stats, "validation": _STORE.validation})


def find_competition_index(name: Optional[str] = None, country: Optional[str] = None, ctype: Optional[str] = None, competition_id: Optional[int] = None) -> ToolResponse:
    try:
        _STORE.ensure_loaded()
    except FileNotFoundError:
        return _err("Index not built.", {})
    by_id = (_STORE.competitions or {}).get("by_id", {})
    by_name = (_STORE.competitions or {}).get("by_name", {})
    by_country = (_STORE.competitions or {}).get("by_country", {})
    by_type = (_STORE.competitions or {}).get("by_type", {})
    results: List[Dict[str, Any]] = []
    ids: List[int] = []
    if competition_id is not None:
        ids = [competition_id] if str(competition_id) in by_id or competition_id in by_id else []
    elif name:
        cid = _best_name_id(by_name, name)
        if cid is not None:
            ids = [cid]
    elif country:
        ids = [int(x) for x in by_country.get(country, [])]
    elif ctype:
        ids = [int(x) for x in by_type.get(ctype, [])]
    else:
        ids = [int(k) for k in by_id.keys() if isinstance(k, int) or k.isdigit()]
    for cid in ids:
        entry = by_id.get(cid) or by_id.get(str(cid))
        if entry:
            results.append(entry)
    return ToolResponse(content=[TextBlock(type="text", text=f"Found {len(results)} competitions.")], metadata={"competitions": results})


def find_season_index(season_label: Optional[str] = None, competition_id: Optional[int] = None, season_id: Optional[int] = None) -> ToolResponse:
    try:
        _STORE.ensure_loaded()
    except FileNotFoundError:
        return _err("Index not built.", {})
    seasons = (_STORE.seasons or {}).get("by_id", {})
    if season_id is not None:
        entry = seasons.get(season_id) or seasons.get(str(season_id))
        rows = [entry] if entry else []
    elif season_label and competition_id is not None:
        # filter seasons by comp id and label
        rows = [s for s in seasons.values() if s.get("competition_id") == competition_id and (s.get("name") or "").lower() == season_label.lower()]
    elif competition_id is not None:
        ids = (_STORE.seasons or {}).get("by_competition", {}).get(str(competition_id), [])
        rows = [seasons.get(s) or seasons.get(str(s)) for s in ids]
        rows = [r for r in rows if r]
    elif season_label:
        ids = (_STORE.seasons or {}).get("by_year", {}).get(season_label, [])
        rows = [seasons.get(s) or seasons.get(str(s)) for s in ids]
        rows = [r for r in rows if r]
    else:
        rows = list(seasons.values())
    return ToolResponse(content=[TextBlock(type="text", text=f"Found {len(rows)} season(s).")], metadata={"seasons": rows})


def find_team_index(name: Optional[str] = None, season_id: Optional[int] = None, competition_id: Optional[int] = None, team_id: Optional[int] = None, country: Optional[str] = None) -> ToolResponse:
    try:
        _STORE.ensure_loaded()
    except FileNotFoundError:
        return _err("Index not built.", {})
    by_id = (_STORE.teams or {}).get("by_id", {})
    by_name = (_STORE.teams or {}).get("by_name", {})
    by_country = (_STORE.teams or {}).get("by_country", {})
    by_season = (_STORE.teams or {}).get("by_season", {})
    results: List[Dict[str, Any]] = []
    if team_id is not None:
        entry = by_id.get(team_id) or by_id.get(str(team_id))
        if entry:
            results.append(entry)
    elif name:
        tid = _best_name_id(by_name, name)
        if tid is not None:
            entry = by_id.get(tid) or by_id.get(str(tid))
            if entry:
                results.append(entry)
    elif season_id is not None:
        ids = by_season.get(str(season_id), [])
        results = [by_id.get(t) or by_id.get(str(t)) for t in ids]
        results = [r for r in results if r]
    elif country:
        ids = by_country.get(country, [])
        results = [by_id.get(t) or by_id.get(str(t)) for t in ids]
        results = [r for r in results if r]
    else:
        results = list(by_id.values())
    # Optional filter by competition via season linking
    if competition_id is not None:
        results = [r for r in results if competition_id in (r.get("competitions") or [])]
    return ToolResponse(content=[TextBlock(type="text", text=f"Found {len(results)} team(s).")], metadata={"teams": results})


def find_player_index(name: Optional[str] = None, team_id: Optional[int] = None, season_id: Optional[int] = None, country: Optional[str] = None, position: Optional[str] = None, player_id: Optional[int] = None) -> ToolResponse:
    try:
        _STORE.ensure_loaded()
    except FileNotFoundError:
        return _err("Index not built.", {})
    by_id = (_STORE.players or {}).get("by_id", {})
    by_name = (_STORE.players or {}).get("by_name", {})
    by_team = (_STORE.players or {}).get("by_team", {})
    by_season = (_STORE.players or {}).get("by_season", {})
    by_country = (_STORE.players or {}).get("by_country", {})
    by_position = (_STORE.players or {}).get("by_position", {})
    results: List[Dict[str, Any]] = []
    if player_id is not None:
        entry = by_id.get(player_id) or by_id.get(str(player_id))
        if entry:
            results.append(entry)
    elif name:
        pid = _best_name_id(by_name, name)
        if pid is not None:
            entry = by_id.get(pid) or by_id.get(str(pid))
            if entry:
                results.append(entry)
    elif team_id is not None:
        ids = by_team.get(str(team_id), [])
        results = [by_id.get(p) or by_id.get(str(p)) for p in ids]
        results = [r for r in results if r]
    elif season_id is not None:
        ids = by_season.get(str(season_id), [])
        results = [by_id.get(p) or by_id.get(str(p)) for p in ids]
        results = [r for r in results if r]
    elif country is not None:
        ids = by_country.get(country, [])
        results = [by_id.get(p) or by_id.get(str(p)) for p in ids]
        results = [r for r in results if r]
    elif position is not None:
        ids = by_position.get(position, [])
        results = [by_id.get(p) or by_id.get(str(p)) for p in ids]
        results = [r for r in results if r]
    else:
        results = list(by_id.values())
    # Secondary filters
    if team_id is not None:
        results = [r for r in results if team_id in (r.get("teams") or [])]
    if season_id is not None:
        results = [r for r in results if season_id in (r.get("seasons") or [])]
    if country is not None:
        results = [r for r in results if (r.get("country") or "") == country]
    if position is not None:
        results = [r for r in results if position in (r.get("positions") or [])]
    if not results and name:
        fallback = _fallback_player_mapping(name, team_id=team_id, season_id=season_id)
        results.extend(fallback)
    return ToolResponse(content=[TextBlock(type="text", text=f"Found {len(results)} player(s).")], metadata={"players": results})


def list_team_matches_index(team_id: int, season_id: Optional[int] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> ToolResponse:
    try:
        _STORE.ensure_loaded()
    except FileNotFoundError:
        return _err("Index not built.", {})
    by_id = (_STORE.matches or {}).get("by_id", {})
    rels = _STORE.relationships or {}
    season_to_matches = rels.get("season_to_matches", {})
    candidate_match_ids: List[int] = []
    if season_id is not None:
        mids = season_to_matches.get(str(season_id), [])
        candidate_match_ids = [int(m) for m in mids]
    else:
        # all matches filtered by team
        candidate_match_ids = [int(mid) for mid in by_id.keys() if isinstance(mid, int) or (isinstance(mid, str) and mid.isdigit())]
    rows = []
    for mid in candidate_match_ids:
        rec = by_id.get(mid) or by_id.get(str(mid))
        if not rec:
            continue
        if rec.get("home_team_id") != team_id and rec.get("away_team_id") != team_id:
            continue
        d = rec.get("match_date")
        if start_date and d and d < start_date:
            continue
        if end_date and d and d > end_date:
            continue
        rows.append(rec)
    rows.sort(key=lambda r: (r.get("match_date") or ""))
    return ToolResponse(content=[TextBlock(type="text", text=f"Found {len(rows)} match(es).")], metadata={"matches": rows})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_statsbomb_index_tools(
    toolkit: Optional[Toolkit] = None,
    *,
    group_name: str = "statsbomb-index",
    activate: bool = True,
) -> Toolkit:
    toolkit = toolkit or Toolkit()
    try:
        toolkit.create_tool_group(
            group_name,
            description="Offline StatsBomb index lookups (no network).",
            active=activate,
            notes=(
                "Use these tools for instant ID resolution and roster/match lookups. "
                "Data is sourced from prebuilt indices under .cache/db_index/."
            ),
        )
    except ValueError:
        pass

    toolkit.register_tool_function(index_status, group_name=group_name, func_description="Show index generation timestamp and entity counts.")
    toolkit.register_tool_function(find_competition_index, group_name=group_name, func_description="Find competition(s) by name, country, type, or id.")
    toolkit.register_tool_function(find_season_index, group_name=group_name, func_description="Find season(s) by label/year, competition, or id.")
    toolkit.register_tool_function(find_team_index, group_name=group_name, func_description="Find team(s) by name, season, competition, country, or id.")
    toolkit.register_tool_function(find_player_index, group_name=group_name, func_description="Find player(s) by name, team, season, nationality, position, or id.")
    toolkit.register_tool_function(list_team_matches_index, group_name=group_name, func_description="List matches for a team with optional season and date range filters.")

    return toolkit
