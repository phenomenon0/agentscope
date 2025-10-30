from __future__ import annotations

import json
from pathlib import Path

from agentspace.indexes.statsbomb_db_index import (
    StatsBombDBIndexer,
    IndexBuildConfig,
    IndexPaths,
)


class DummyClient:
    def list_competitions(self):
        return [
            {
                "competition_id": 37,
                "competition_name": "FA Women's Super League",
                "country_name": "England",
                "competition_format": "domestic_league",
            }
        ]

    def list_seasons(self, competition_id: int, *, use_cache: bool = True):
        # Simulate endpoint returning no seasons to force fallback
        return []

    def list_matches(self, competition_id: int, season_id: int, *, use_cache: bool = True):
        # Also empty so mapping has to provide matches
        return []

    def get_player_mapping(
        self,
        *,
        competition_id: int | None = None,
        season_id: int | None = None,
        live_player_id: int | None = None,
        offline_player_id: int | None = None,
        match_date_from: str | None = None,
        match_date_to: str | None = None,
        all_account_data: bool = False,
        add_matches_played: bool = False,
        use_cache: bool = True,
    ):
        # Provide minimal mapping rows spanning two teams and two matches
        rows = []
        if all_account_data and season_id is None:
            # derive seasons
            rows.append(
                {
                    "competition_id": 37,
                    "competition_name": "FA Women's Super League",
                    "season_id": 90,
                    "season_name": "2020/2021",
                    "offline_team_id": 746,
                    "team_name": "Manchester City WFC",
                    "offline_player_id": 10172,
                    "player_name": "Jill Scott",
                }
            )
        if season_id == 90 and add_matches_played:
            rows.extend(
                [
                    {
                        "competition_id": 37,
                        "competition_name": "FA Women's Super League",
                        "season_id": 90,
                        "season_name": "2020/2021",
                        "offline_team_id": 746,
                        "team_name": "Manchester City WFC",
                        "offline_player_id": 10172,
                        "player_name": "Jill Scott",
                        "earliest_match_date": "2020-09-05",
                        "most_recent_match_date": "2021-01-17",
                        "matches_played": [
                            {"offline_match_id": 3764234, "match_date": "2020-09-05"},
                            {"offline_match_id": 3775611, "match_date": "2021-01-17"},
                        ],
                    },
                    {
                        "competition_id": 37,
                        "competition_name": "FA Women's Super League",
                        "season_id": 90,
                        "season_name": "2020/2021",
                        "offline_team_id": 967,
                        "team_name": "Everton LFC",
                        "offline_player_id": 10172,
                        "player_name": "Jill Scott",
                        "earliest_match_date": "2021-01-31",
                        "most_recent_match_date": "2021-05-09",
                        "matches_played": [
                            {"offline_match_id": 3775563, "match_date": "2021-05-09"}
                        ],
                    },
                ]
            )
        return rows


def test_db_index_fallback_to_player_mapping(tmp_path: Path):
    paths = IndexPaths(base_dir=tmp_path / "db_index")
    cfg = IndexBuildConfig(
        competitions=[37],
        include_player_stats=False,
        include_lineups=False,
        include_player_mapping=True,
        paths=paths,
    )
    indexer = StatsBombDBIndexer(cfg)
    # Inject dummy client to avoid network
    indexer.client = DummyClient()
    indexer.build()

    # Validate files wrote
    for p in [
        paths.competitions,
        paths.seasons,
        paths.teams,
        paths.players,
        paths.matches,
        paths.relationships,
        paths.stats,
        paths.validation,
    ]:
        assert p.exists(), f"missing {p}"

    players = json.loads(paths.players.read_text())
    seasons = json.loads(paths.seasons.read_text())
    rels = json.loads(paths.relationships.read_text())

    # Player present by id and by name
    pid = 10172
    assert str(pid) in players["by_id"] or pid in players["by_id"]
    # name index is case-insensitive canonicalized; check a few variants
    by_name = players["by_name"]
    assert by_name.get("Jill Scott") == pid or by_name.get("jill scott") == pid or by_name.get("jillscott") == pid

    # Season derived from mapping
    assert 90 in seasons["by_competition"]["37"]

    # Relationships: season contains player and matches
    assert str(pid) in {str(x) for x in rels["season_to_players"]["90"]}
    assert rels["season_to_matches"]["90"], "season_to_matches should not be empty"
