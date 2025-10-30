"""
Agentscope toolkit: Online StatsBomb index lookups via Player Mapping API.

These tools query StatsBomb's Player Mapping endpoint for fast, live ID
resolution without building local indices. They are read-only and avoid
heavy endpoints, returning small, structured metadata for the agent.

Name matching uses the shared canonicaliser from ``services.statsbomb_tools``
to robustly handle diacritics and special letters (Nordic, Turkish, CEE, etc.).
When no exact match is found, a similarity-based fallback returns the closest
match instead of an empty result, reducing false negatives like "Yıldız" vs
"Yildiz".
"""

import difflib
from typing import Any, Dict, List, Optional

from agentscope.message import TextBlock
from agentscope.tool import Toolkit, ToolResponse

from ..clients.statsbomb import StatsBombClient
from ..services.statsbomb_tools import _canonical as _sb_canonical


def _canonical(s: str) -> str:
    """Shared canonicaliser that normalises diacritics and spacing.

    Falls back to lower/strip/split if the shared helper is unavailable.
    """
    try:
        return _sb_canonical(s or "")
    except Exception:
        return " ".join((s or "").lower().strip().split())


def _best_name_match(rows: List[Dict[str, Any]], key: str, query: str) -> List[Dict[str, Any]]:
    """Return best matching rows by name with robust fallback.

    Strategy:
    - Exact canonical match wins.
    - Otherwise, rank by similarity of de-spaced canonical forms + token overlap.
    - Return top-k (default: up to 5); if nothing clears a cutoff, still return the best 1.
    """
    if not query:
        return rows
    q = _canonical(query)
    # exact canonical matches first
    exact = [r for r in rows if _canonical(str(r.get(key, ""))) == q]
    if exact:
        return exact

    # Score all rows by similarity
    scored: List[tuple[float, Dict[str, Any]]] = []
    q_ds = q.replace(" ", "")
    q_tokens = set(q.split())
    for r in rows:
        name = str(r.get(key, ""))
        cn = _canonical(name)
        if not cn:
            continue
        cn_ds = cn.replace(" ", "")
        sim = difflib.SequenceMatcher(a=q_ds, b=cn_ds).ratio()
        token_overlap = 1.0 if (q_tokens and (q_tokens & set(cn.split()))) else 0.0
        score = sim + 0.25 * token_overlap
        scored.append((score, r))

    if not scored:
        return []

    scored.sort(key=lambda x: x[0], reverse=True)
    # Choose a conservative cutoff; still return at least the best one
    cutoff = 0.80
    top = [r for s, r in scored if s >= cutoff][:5]
    if top:
        return top
    # Fallback: return the best single candidate
    return [scored[0][1]]


def _response(lines: List[str], metadata: Dict[str, Any]) -> ToolResponse:
    return ToolResponse(content=[TextBlock(type="text", text="\n".join(lines))], metadata=metadata)


def online_index_status(
    competition_id: Optional[int] = None,
    season_id: Optional[int] = None,
    sample: int = 3,
    use_cache: bool = True,
) -> ToolResponse:
    """Probe the Player Mapping API and return a small sample and counts."""
    client = StatsBombClient()
    rows = client.get_player_mapping(
        competition_id=competition_id,
        season_id=season_id,
        all_account_data=True,
        add_matches_played=False,
        use_cache=use_cache,
    )
    lines = [
        f"Player Mapping online index: {len(rows)} row(s) available for filters.",
        "Preview:",
    ]
    for r in rows[: max(0, sample)]:
        lines.append(
            f"- {r.get('player_name','?')} (player_id={r.get('offline_player_id','?')}, "
            f"team={r.get('team_name','?')}, season={r.get('season_name','?')})"
        )
    return _response(lines, {"count": len(rows), "sample": rows[:sample]})


def list_seasons_online(
    competition_id: int,
    use_cache: bool = True,
) -> ToolResponse:
    """List seasons for a competition using the mapping API."""
    client = StatsBombClient()
    rows = client.get_player_mapping(
        competition_id=competition_id,
        all_account_data=True,
        use_cache=use_cache,
    )
    seen: Dict[int, str] = {}
    for r in rows:
        sid = r.get("season_id")
        sname = r.get("season_name")
        if isinstance(sid, int) and sid not in seen:
            seen[sid] = sname
    seasons = [{"season_id": k, "season_name": v} for k, v in seen.items()]
    lines = [f"Found {len(seasons)} season(s) for competition {competition_id}."]
    for s in sorted(seasons, key=lambda x: x["season_id"])[:5]:
        lines.append(f"- {s['season_id']}: {s['season_name']}")
    return _response(lines, {"competition_id": competition_id, "seasons": seasons})


def find_player_online(
    name: str,
    competition_id: int,
    season_id: int,
    add_matches_played: bool = False,
    use_cache: bool = True,
) -> ToolResponse:
    """Find player(s) by name using mapping API within a comp-season."""
    client = StatsBombClient()
    rows = client.get_player_mapping(
        competition_id=competition_id,
        season_id=season_id,
        all_account_data=True,
        add_matches_played=add_matches_played,
        use_cache=use_cache,
    )
    matched = _best_name_match(rows, "player_name", name)
    players = []
    for r in matched:
        players.append(
            {
                "offline_player_id": r.get("offline_player_id"),
                "player_name": r.get("player_name"),
                "team_id": r.get("offline_team_id"),
                "team_name": r.get("team_name"),
                "season_id": r.get("season_id"),
                "season_name": r.get("season_name"),
                "most_recent_match_date": r.get("most_recent_match_date"),
            }
        )
    lines = [
        f"Found {len(players)} mapping row(s) for '{name}' in comp {competition_id} season {season_id}.",
    ]
    for p in players[:5]:
        lines.append(
            f"- {p['player_name']} (id={p['offline_player_id']}), team={p['team_name']}, last={p['most_recent_match_date']}"
        )
    return _response(lines, {"players": players})


def find_team_players_online(
    team_name: str,
    competition_id: int,
    season_id: int,
    use_cache: bool = True,
) -> ToolResponse:
    """List players for a team in a comp-season via mapping API."""
    client = StatsBombClient()
    rows = client.get_player_mapping(
        competition_id=competition_id,
        season_id=season_id,
        all_account_data=True,
        add_matches_played=False,
        use_cache=use_cache,
    )
    team_rows = _best_name_match(rows, "team_name", team_name)
    seen: Dict[int, Dict[str, Any]] = {}
    for r in team_rows:
        pid = r.get("offline_player_id")
        if isinstance(pid, int) and pid not in seen:
            seen[pid] = {
                "offline_player_id": pid,
                "player_name": r.get("player_name"),
                "team_id": r.get("offline_team_id"),
                "team_name": r.get("team_name"),
            }
    players = list(seen.values())
    lines = [
        f"Found {len(players)} player(s) for team '{team_name}' in comp {competition_id} season {season_id}.",
    ]
    for p in players[:5]:
        lines.append(f"- {p['player_name']} (id={p['offline_player_id']})")
    return _response(lines, {"team": team_name, "competition_id": competition_id, "season_id": season_id, "players": players})


def get_player_matches_online(
    offline_player_id: int,
    competition_id: int,
    season_id: int,
    use_cache: bool = True,
) -> ToolResponse:
    """Return matches for a player in a comp-season via mapping API."""
    client = StatsBombClient()
    rows = client.get_player_mapping(
        competition_id=competition_id,
        season_id=season_id,
        offline_player_id=offline_player_id,
        add_matches_played=True,
        use_cache=use_cache,
    )
    matches: Dict[int, str] = {}
    for r in rows:
        for m in r.get("matches_played") or []:
            mid = m.get("offline_match_id")
            date = m.get("match_date")
            if isinstance(mid, int):
                matches[mid] = date
    match_rows = [
        {"offline_match_id": mid, "match_date": date} for mid, date in sorted(matches.items())
    ]
    lines = [
        f"Found {len(match_rows)} match(es) for player {offline_player_id} in comp {competition_id} season {season_id}.",
    ]
    for m in match_rows[:5]:
        lines.append(f"- {m['offline_match_id']} @ {m['match_date']}")
    return _response(lines, {"player_id": offline_player_id, "matches": match_rows})


def resolve_player_current_team_online(
    offline_player_id: int,
    competition_id: Optional[int] = None,
    season_id: Optional[int] = None,
    use_cache: bool = True,
) -> ToolResponse:
    """Infer player's current team using most_recent_match_date from mapping API."""
    client = StatsBombClient()
    rows = client.get_player_mapping(
        competition_id=competition_id,
        season_id=season_id,
        offline_player_id=offline_player_id,
        all_account_data=competition_id is None and season_id is None,
        add_matches_played=False,
        use_cache=use_cache,
    )
    best = None
    for r in rows:
        cur = r.get("most_recent_match_date") or ""
        if not best:
            best = r
        else:
            if (cur or "") > (best.get("most_recent_match_date") or ""):
                best = r
    if not best:
        return _response([f"No mapping rows found for player {offline_player_id}."], {"player_id": offline_player_id})
    lines = [
        f"Resolved current team for player {offline_player_id}: {best.get('team_name')} (team_id={best.get('offline_team_id')}).",
    ]
    meta = {
        "player_id": offline_player_id,
        "team_id": best.get("offline_team_id"),
        "team_name": best.get("team_name"),
        "most_recent_match_date": best.get("most_recent_match_date"),
    }
    return _response(lines, meta)


def register_statsbomb_online_index_tools(
    toolkit: Optional[Toolkit] = None,
    *,
    group_name: str = "statsbomb-online-index",
    activate: bool = True,
) -> Toolkit:
    toolkit = toolkit or Toolkit()
    try:
        toolkit.create_tool_group(
            group_name,
            description="Online StatsBomb index lookups via Player Mapping API.",
            active=activate,
            notes=(
                "These tools resolve IDs and rosters without building local indices. "
                "Provide competition_id and season_id for narrow queries."
            ),
        )
    except ValueError:
        pass

    toolkit.register_tool_function(online_index_status, group_name=group_name, func_description="Probe Player Mapping API and return counts/sample.")
    toolkit.register_tool_function(list_seasons_online, group_name=group_name, func_description="List seasons for a competition using mapping API.")
    toolkit.register_tool_function(find_player_online, group_name=group_name, func_description="Find player(s) by name within a competition season.")
    toolkit.register_tool_function(find_team_players_online, group_name=group_name, func_description="List players for a team in a competition season.")
    toolkit.register_tool_function(get_player_matches_online, group_name=group_name, func_description="List matches for a player in a competition season.")
    toolkit.register_tool_function(resolve_player_current_team_online, group_name=group_name, func_description="Resolve player's current team using mapping API.")
    return toolkit
