from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from agentscope.tool import Toolkit

from agentspace.agent_tools.offline_sqlite import (
    OfflineSQLiteIndex,
    _INDEX_STORE,
    offline_index_status,
    register_offline_index_tools,
    search_competitions_tool,
    search_matches_tool,
    search_match_players_tool,
    search_players_tool,
    search_teams_tool,
)
from agentspace.indexes.offline_sqlite_index import OfflineIndexBuilder


class FakeStatsBombClient:
    def __init__(self) -> None:
        self._competitions = [
            {
                "competition_id": 2,
                "competition_name": "Premier League",
                "country_name": "England",
                "competition_format": "domestic league",
            }
        ]

        self._seasons = [
            {
                "season_id": 281,
                "season_name": "2023/2024",
            }
        ]

        self._team_stats = [
            {"team_id": 746, "team_name": "Arsenal"},
            {"team_id": 745, "team_name": "Manchester City"},
        ]

        self._player_stats = [
            {
                "player_id": 1,
                "player_name": "Bukayo Saka",
                "team_id": 746,
                "team_name": "Arsenal",
                "player_season_minutes": 2800,
                "position": "RW",
            },
            {
                "player_id": 2,
                "player_name": "Martin Ødegaard",
                "team_id": 746,
                "team_name": "Arsenal",
                "player_season_minutes": 3000,
                "position": "AM",
            },
            {
                "player_id": 3,
                "player_name": "Erling Haaland",
                "team_id": 745,
                "team_name": "Manchester City",
                "player_season_minutes": 2600,
                "position": "ST",
            },
        ]
        self._matches = [
            {
                "match_id": 1,
                "match_date": "2024-05-19",
                "kick_off": "14:00:00.000",
                "competition_stage": {"name": "Regular Season"},
                "match_status": "available",
                "home_team": {
                    "home_team_id": 746,
                    "home_team_name": "Arsenal",
                },
                "away_team": {
                    "away_team_id": 745,
                    "away_team_name": "Manchester City",
                },
                "home_score": 2,
                "away_score": 1,
            }
        ]
        self._lineups = {
            1: [
                {
                    "team_id": 746,
                    "team_name": "Arsenal",
                    "lineup": [
                        {
                            "player_id": 1,
                            "player_name": "Bukayo Saka",
                            "positions": [
                                {
                                    "position": "Right Wing",
                                    "start_reason": "Starting XI",
                                }
                            ],
                            "jersey_number": 7,
                        },
                        {
                            "player_id": 2,
                            "player_name": "Martin Ødegaard",
                            "positions": [
                                {
                                    "position": "Attacking Midfield",
                                    "start_reason": "Starting XI",
                                }
                            ],
                            "jersey_number": 8,
                        },
                        {
                            "player_id": 4,
                            "player_name": "Emile Smith Rowe",
                            "positions": [
                                {
                                    "position": "Left Wing",
                                    "start_reason": "Substitute",
                                }
                            ],
                            "jersey_number": 10,
                        },
                    ],
                },
                {
                    "team_id": 745,
                    "team_name": "Manchester City",
                    "lineup": [
                        {
                            "player_id": 3,
                            "player_name": "Erling Haaland",
                            "positions": [
                                {
                                    "position": "Striker",
                                    "start_reason": "Starting XI",
                                }
                            ],
                            "jersey_number": 9,
                        }
                    ],
                },
            ]
        }
        self._mapping_rows = [
            {
                "competition_id": 2,
                "competition_name": "Premier League",
                "season_id": 281,
                "season_name": "2023/2024",
                "offline_team_id": 746,
                "team_name": "Arsenal",
                "offline_player_id": 1,
                "player_name": "Bukayo Saka",
                "player_position": "RW",
                "minutes_played": 2800,
            },
            {
                "competition_id": 2,
                "competition_name": "Premier League",
                "season_id": 281,
                "season_name": "2023/2024",
                "offline_team_id": 746,
                "team_name": "Arsenal",
                "offline_player_id": 2,
                "player_name": "Martin Ødegaard",
                "player_position": "AM",
                "minutes_played": 3000,
            },
            {
                "competition_id": 2,
                "competition_name": "Premier League",
                "season_id": 281,
                "season_name": "2023/2024",
                "offline_team_id": 745,
                "team_name": "Manchester City",
                "offline_player_id": 3,
                "player_name": "Erling Haaland",
                "player_position": "ST",
                "minutes_played": 2600,
            },
        ]

    # StatsBomb client interface -------------------------------------------------

    def list_competitions(self, *, use_cache: bool = True) -> List[Dict[str, Any]]:
        return self._competitions

    def list_seasons(self, competition_id: int, *, use_cache: bool = True) -> List[Dict[str, Any]]:
        return self._seasons

    def get_team_season_stats(
        self,
        competition_id: int,
        season_id: int,
        *,
        use_cache: bool = True,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self._team_stats

    def get_player_season_stats(
        self,
        competition_id: int,
        season_id: int,
        *,
        use_cache: bool = True,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self._player_stats

    def get_player_mapping(
        self,
        competition_id: Optional[int] = None,
        season_id: Optional[int] = None,
        *,
        all_account_data: bool = True,
        add_matches_played: bool = False,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        rows = self._mapping_rows
        if competition_id is not None:
            rows = [r for r in rows if r.get("competition_id") == competition_id]
        if season_id is not None:
            rows = [r for r in rows if r.get("season_id") == season_id]
        return rows

    def list_matches(
        self, competition_id: int, season_id: int, *, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        return self._matches

    def get_lineups(self, match_id: int, *, use_cache: bool = True) -> List[Dict[str, Any]]:
        return self._lineups.get(match_id, [])


def test_offline_index_builder_and_tools(tmp_path: Path) -> None:
    db_path = tmp_path / "offline.sqlite"
    builder = OfflineIndexBuilder(
        db_path=db_path,
        client=FakeStatsBombClient(),
    )
    path = builder.build()
    assert path.exists()

    index = OfflineSQLiteIndex(db_path=path)
    competitions = index.search_competitions("Premier")
    assert competitions and competitions[0]["competition_name"] == "Premier League"

    teams = index.search_teams("Arsenal")
    assert teams and teams[0]["team_name"] == "Arsenal"

    players = index.search_players("Haaland")
    assert any(row["player_name"] == "Erling Haaland" for row in players)

    # Configure tools against the temporary database
    toolkit = register_offline_index_tools(Toolkit(), db_path=path, activate=True)
    _INDEX_STORE._connection = None  # ensure clean handle

    status = offline_index_status()
    assert "Competitions indexed" in status.content[0]["text"]

    comp_resp = search_competitions_tool("Premier")
    assert "Premier League" in comp_resp.content[0]["text"]

    team_resp = search_teams_tool("Arsenal")
    assert "Arsenal" in team_resp.content[0]["text"]

    player_resp = search_players_tool("Saka")
    assert "Bukayo Saka" in player_resp.content[0]["text"]

    matches = _INDEX_STORE.search_matches(competition_id=2, season_id=281)
    assert matches and matches[0]["match_id"] == 1

    match_players = _INDEX_STORE.search_match_players(match_id=1)
    assert any(row["player_name"] == "Emile Smith Rowe" for row in match_players)

    matches_resp = search_matches_tool(competition_id=2)
    assert "Premier League" in matches_resp.content[0]["text"]

    participants_resp = search_match_players_tool(match_id=1)
    assert "Emile Smith Rowe" in participants_resp.content[0]["text"]
