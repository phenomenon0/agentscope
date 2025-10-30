"""
AgentScope tools for querying the offline SQLite index created by
`agentspace.indexes.offline_sqlite_index`.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from agentscope.message import TextBlock
from agentscope.tool import Toolkit, ToolResponse


DEFAULT_DB_PATH = Path(".cache/offline_index/top_competitions.sqlite")


def _fts_query(query: str) -> str:
    terms = [token.strip() for token in query.split() if token.strip()]
    if not terms:
        return ""
    return " ".join(f"{term}*" for term in terms)


@dataclass
class OfflineSQLiteIndex:
    db_path: Path = DEFAULT_DB_PATH
    _connection: sqlite3.Connection | None = None

    def ensure_connection(self) -> sqlite3.Connection:
        if self._connection:
            return self._connection
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Offline index database not found at {self.db_path}. "
                "Build it with `python -m agentspace.indexes.offline_sqlite_index`."
            )
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        self._connection = conn
        return conn

    # ------------------------------------------------------------------ queries

    def search_competitions(self, query: str | None, limit: int = 10) -> List[Dict[str, Any]]:
        conn = self.ensure_connection()
        if query:
            sql = """
                SELECT
                    c.competition_id,
                    c.competition_name,
                    c.season_name,
                    c.season_id,
                    c.competition_category,
                    c.country,
                    bm25(competitions_fts) AS score
                FROM competitions_fts
                JOIN competitions c ON c.id = competitions_fts.rowid
                WHERE competitions_fts MATCH ?
                ORDER BY score
                LIMIT ?
            """
            rows = conn.execute(sql, (_fts_query(query), limit)).fetchall()
        else:
            sql = """
                SELECT
                    competition_id,
                    competition_name,
                    season_name,
                    season_id,
                    competition_category,
                    country
                FROM competitions
                ORDER BY season_id DESC
                LIMIT ?
            """
            rows = conn.execute(sql, (limit,)).fetchall()
        return [dict(row) for row in rows]

    def search_teams(
        self,
        query: str | None,
        *,
        competition_id: int | None = None,
        season_id: int | None = None,
        season_name: str | None = None,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        conn = self.ensure_connection()
        params: List[Any] = []
        filters: List[str] = []
        order_clause = "ORDER BY score"

        if query:
            filters.append("teams_fts MATCH ?")
            params.append(_fts_query(query))
            base = """
                SELECT
                    t.team_id,
                    t.team_name,
                    t.competition_id,
                    t.competition_name,
                    t.season_id,
                    t.season_name,
                    bm25(teams_fts) AS score
                FROM teams_fts
                JOIN teams t ON t.id = teams_fts.rowid
            """
        else:
            order_clause = "ORDER BY t.season_id DESC"
            base = """
                SELECT
                    t.team_id,
                    t.team_name,
                    t.competition_id,
                    t.competition_name,
                    t.season_id,
                    t.season_name,
                    0.0 AS score
                FROM teams t
            """

        if competition_id is not None:
            filters.append("t.competition_id = ?")
            params.append(int(competition_id))
        if season_id is not None:
            filters.append("t.season_id = ?")
            params.append(int(season_id))
        if season_name:
            filters.append("t.season_name = ?")
            params.append(season_name)

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        sql = f"""
            {base}
            {where_clause}
            {order_clause}
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def search_players(
        self,
        query: str | None,
        *,
        team_id: int | None = None,
        competition_id: int | None = None,
        season_id: int | None = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        conn = self.ensure_connection()
        params: List[Any] = []
        filters: List[str] = []
        order_clause = "ORDER BY score"

        if query:
            filters.append("players_fts MATCH ?")
            params.append(_fts_query(query))
            base = """
                SELECT
                    p.player_id,
                    p.player_name,
                    p.team_id,
                    p.team_name,
                    p.competition_id,
                    p.competition_name,
                    p.season_id,
                    p.season_name,
                    p.position,
                    p.minutes,
                    bm25(players_fts) AS score
                FROM players_fts
                JOIN players p ON p.id = players_fts.rowid
            """
        else:
            order_clause = "ORDER BY (p.minutes IS NULL), p.minutes DESC, p.player_name"
            base = """
                SELECT
                    p.player_id,
                    p.player_name,
                    p.team_id,
                    p.team_name,
                    p.competition_id,
                    p.competition_name,
                    p.season_id,
                    p.season_name,
                    p.position,
                    p.minutes,
                    0.0 AS score
                FROM players p
            """

        if team_id is not None:
            filters.append("p.team_id = ?")
            params.append(int(team_id))
        if competition_id is not None:
            filters.append("p.competition_id = ?")
            params.append(int(competition_id))
        if season_id is not None:
            filters.append("p.season_id = ?")
            params.append(int(season_id))

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        sql = f"""
            {base}
            {where_clause}
            {order_clause}
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def search_matches(
        self,
        *,
        competition_id: int | None = None,
        season_id: int | None = None,
        team_id: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        conn = self.ensure_connection()
        clauses: List[str] = []
        params: List[Any] = []
        if competition_id is not None:
            clauses.append("competition_id = ?")
            params.append(int(competition_id))
        if season_id is not None:
            clauses.append("season_id = ?")
            params.append(int(season_id))
        if team_id is not None:
            clauses.append("(home_team_id = ? OR away_team_id = ?)")
            params.extend((int(team_id), int(team_id)))
        if start_date:
            clauses.append("match_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("match_date <= ?")
            params.append(end_date)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT
                match_id,
                match_date,
                competition_id,
                competition_name,
                season_id,
                season_name,
                home_team_id,
                home_team_name,
                away_team_id,
                away_team_name,
                home_score,
                away_score,
                competition_stage
            FROM matches
            {where}
            ORDER BY match_date DESC, match_id DESC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def search_match_players(
        self,
        *,
        match_id: int,
        team_id: int | None = None,
        starters_only: bool = False,
        limit: int = 40,
    ) -> List[Dict[str, Any]]:
        conn = self.ensure_connection()
        clauses = ["match_id = ?"]
        params: List[Any] = [int(match_id)]
        if team_id is not None:
            clauses.append("team_id = ?")
            params.append(int(team_id))
        if starters_only:
            clauses.append("is_starter = 1")
        where = " AND ".join(clauses)
        sql = f"""
            SELECT
                match_id,
                player_id,
                player_name,
                team_id,
                team_name,
                position,
                jersey_number,
                is_starter,
                minutes_played
            FROM match_players
            WHERE {where}
            ORDER BY is_starter DESC, minutes_played DESC, player_name
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


_INDEX_STORE = OfflineSQLiteIndex()


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def offline_index_status() -> ToolResponse:
    try:
        conn = _INDEX_STORE.ensure_connection()
    except FileNotFoundError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=str(exc))],
            metadata={"db_path": str(_INDEX_STORE.db_path)},
        )

    cursor = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM competitions) AS competitions,
            (SELECT COUNT(*) FROM teams) AS teams,
            (SELECT COUNT(*) FROM players) AS players
        """
    )
    row = cursor.fetchone() or {}
    lines = [
        f"Database path: { _INDEX_STORE.db_path }",
        f"Competitions indexed: {row.get('competitions', 0)}",
        f"Teams indexed: {row.get('teams', 0)}",
        f"Players indexed: {row.get('players', 0)}",
    ]
    return ToolResponse(
        content=[TextBlock(type="text", text="\n".join(lines))],
        metadata={"counts": dict(row)},
    )


def search_competitions_tool(query: str | None = None, limit: int = 10) -> ToolResponse:
    try:
        rows = _INDEX_STORE.search_competitions(query or "", limit)
    except FileNotFoundError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=str(exc))],
            metadata={"db_path": str(_INDEX_STORE.db_path)},
        )

    if not rows:
        return ToolResponse(
            content=[TextBlock(type="text", text="No competitions matched the query.")],
            metadata={"query": query},
        )

    lines = [
        f"{row['competition_name']} — {row['season_name']} (competition_id={row['competition_id']}, season_id={row['season_id']}, type={row['competition_category']})"
        for row in rows
    ]
    return ToolResponse(
        content=[TextBlock(type="text", text="\n".join(lines))],
        metadata={"results": rows, "query": query},
    )


def search_teams_tool(
    query: str | None = None,
    competition_id: int | None = None,
    season_id: int | None = None,
    season_name: str | None = None,
    limit: int = 15,
) -> ToolResponse:
    try:
        rows = _INDEX_STORE.search_teams(
            query or "",
            competition_id=competition_id,
            season_id=season_id,
            season_name=season_name,
            limit=limit,
        )
    except FileNotFoundError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=str(exc))],
            metadata={"db_path": str(_INDEX_STORE.db_path)},
        )

    if not rows:
        return ToolResponse(
            content=[TextBlock(type="text", text="No teams matched the query.")],
            metadata={
                "query": query,
                "competition_id": competition_id,
                "season_id": season_id,
                "season_name": season_name,
            },
        )

    lines = [
        f"{row['team_name']} — {row['competition_name']} {row['season_name']} (team_id={row['team_id']}, competition_id={row['competition_id']}, season_id={row['season_id']})"
        for row in rows
    ]
    return ToolResponse(
        content=[TextBlock(type="text", text="\n".join(lines))],
        metadata={"results": rows, "query": query},
    )


def search_players_tool(
    query: str | None = None,
    team_id: int | None = None,
    competition_id: int | None = None,
    season_id: int | None = None,
    limit: int = 20,
) -> ToolResponse:
    try:
        rows = _INDEX_STORE.search_players(
            query or "",
            team_id=team_id,
            competition_id=competition_id,
            season_id=season_id,
            limit=limit,
        )
    except FileNotFoundError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=str(exc))],
            metadata={"db_path": str(_INDEX_STORE.db_path)},
        )

    if not rows:
        return ToolResponse(
            content=[TextBlock(type="text", text="No players matched the query.")],
            metadata={
                "query": query,
                "team_id": team_id,
                "competition_id": competition_id,
                "season_id": season_id,
            },
        )

    def _format_minutes(value: Any) -> str:
        if value is None:
            return "n/a"
        return f"{float(value):.0f}"

    lines = [
        (
            f"{row['player_name']} — {row.get('team_name') or 'Unknown'}"
            f" ({row['competition_name']} {row['season_name']}, player_id={row['player_id']}, "
            f"team_id={row.get('team_id')}, minutes={_format_minutes(row.get('minutes'))})"
        )
        for row in rows
    ]
    return ToolResponse(
        content=[TextBlock(type="text", text="\n".join(lines))],
        metadata={"results": rows, "query": query},
    )


def search_matches_tool(
    competition_id: int | None = None,
    season_id: int | None = None,
    team_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
) -> ToolResponse:
    try:
        rows = _INDEX_STORE.search_matches(
            competition_id=competition_id,
            season_id=season_id,
            team_id=team_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    except FileNotFoundError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=str(exc))],
            metadata={"db_path": str(_INDEX_STORE.db_path)},
        )
    if not rows:
        return ToolResponse(
            content=[TextBlock(type="text", text="No matches found in the offline index.")],
            metadata={
                "competition_id": competition_id,
                "season_id": season_id,
                "team_id": team_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
    lines = [
        (
            f"{row['match_date']} — {row['home_team_name'] or 'TBD'} vs {row['away_team_name'] or 'TBD'}"
            f" (match_id={row['match_id']}, competition={row['competition_name']}, season={row['season_name']},"
            f" score={row.get('home_score')}–{row.get('away_score')})"
        )
        for row in rows
    ]
    return ToolResponse(
        content=[TextBlock(type="text", text="\n".join(lines))],
        metadata={"results": rows},
    )


def search_match_players_tool(
    match_id: int,
    team_id: int | None = None,
    starters_only: bool = False,
    limit: int = 40,
) -> ToolResponse:
    try:
        rows = _INDEX_STORE.search_match_players(
            match_id=match_id,
            team_id=team_id,
            starters_only=starters_only,
            limit=limit,
        )
    except FileNotFoundError as exc:
        return ToolResponse(
            content=[TextBlock(type="text", text=str(exc))],
            metadata={"db_path": str(_INDEX_STORE.db_path)},
        )
    if not rows:
        return ToolResponse(
            content=[TextBlock(type="text", text="No match participants found in the offline index.")],
            metadata={"match_id": match_id, "team_id": team_id, "starters_only": starters_only},
        )
    lines = [
        (
            f"{row['player_name']} — {row.get('team_name') or 'Unknown'}"
            f" (player_id={row['player_id']}, starter={'yes' if row['is_starter'] else 'no'}, minutes={row.get('minutes_played') or 'n/a'})"
        )
        for row in rows
    ]
    return ToolResponse(
        content=[TextBlock(type="text", text="\n".join(lines))],
        metadata={"results": rows},
    )


# ---------------------------------------------------------------------------
# Toolkit registration
# ---------------------------------------------------------------------------


def register_offline_index_tools(
    toolkit: Toolkit | None = None,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    group_name: str = "offline-index",
    activate: bool = True,
) -> Toolkit:
    """
    Register offline lookup tools on the provided toolkit.
    """

    toolkit = toolkit or Toolkit()
    _INDEX_STORE.db_path = Path(db_path)

    if group_name not in toolkit.groups:
        toolkit.create_tool_group(
            group_name,
            description="Offline lookup tools backed by SQLite (competitions, teams, players).",
            active=activate,
        )
    else:
        toolkit.update_tool_groups([group_name], activate)

    toolkit.register_tool_function(
        offline_index_status,
        group_name=group_name,
        func_description="Show counts and status information for the offline SQLite index.",
    )
    toolkit.register_tool_function(
        search_competitions_tool,
        group_name=group_name,
        func_description="Search competitions in the offline SQLite index.",
    )
    toolkit.register_tool_function(
        search_teams_tool,
        group_name=group_name,
        func_description="Search teams in the offline SQLite index.",
    )
    toolkit.register_tool_function(
        search_players_tool,
        group_name=group_name,
        func_description="Search players in the offline SQLite index.",
    )
    toolkit.register_tool_function(
        search_matches_tool,
        group_name=group_name,
        func_description="Search matches stored in the offline SQLite index.",
    )
    toolkit.register_tool_function(
        search_match_players_tool,
        group_name=group_name,
        func_description="List player appearances for an indexed match (includes substitutes).",
    )
    return toolkit
