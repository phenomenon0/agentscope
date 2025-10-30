import pytest

from agentspace.services import team_context


def test_load_team_context_success(monkeypatch):
    monkeypatch.setattr(
        team_context,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )

    monkeypatch.setattr(
        team_context,
        "fetch_team_season_stats_data",
        lambda competition_id, season_id, use_cache=True: [
            {
                "team_name": "Arsenal",
                "team_season_points": 25,
                "team_season_goals": 20,
                "team_season_goals_against": 10,
                "team_season_matches": 10,
            },
            {
                "team_name": "Chelsea",
                "team_season_points": 22,
                "team_season_goals": 18,
                "team_season_goals_against": 12,
                "team_season_matches": 10,
            },
        ],
    )

    monkeypatch.setattr(
        team_context,
        "get_competition_players",
        lambda **kwargs: [
            {
                "player_name": "Bukayo Saka",
                "position": "FW",
                "player_season_minutes": 900,
                "player_season_goals": 7,
                "player_season_assists": 5,
            },
            {
                "player_name": "Declan Rice",
                "position": "MF",
                "player_season_minutes": 880,
                "player_season_goals": 2,
                "player_season_assists": 3,
            },
        ],
    )

    monkeypatch.setattr(
        team_context,
        "list_matches",
        lambda competition_id, season_id, team_name=None, use_cache=True: [
            {
                "match_id": 1,
                "match_date": "2024-08-15",
                "kick_off": "15:00:00",
                "home_team": {"home_team_name": "Arsenal"},
                "away_team": {"away_team_name": "Everton"},
                "home_score": 2,
                "away_score": 0,
                "match_status": "available",
            },
            {
                "match_id": 2,
                "match_date": "2024-08-22",
                "kick_off": "15:00:00",
                "home_team": {"home_team_name": "Chelsea"},
                "away_team": {"away_team_name": "Arsenal"},
                "home_score": None,
                "away_score": None,
                "match_status": "scheduled",
            },
        ],
    )

    monkeypatch.setattr(
        team_context,
        "list_competitions",
        lambda use_cache=True: [
            {"competition_id": 2, "competition_name": "Premier League"},
        ],
    )

    context = team_context.load_team_context(2, "2024/2025", "Arsenal")

    assert context["season_id"] == 317
    assert context["table_position"] == 1
    assert context["table_size"] == 2
    assert context["team_summary"]["team_name"] == "Arsenal"
    assert context["record"]["won"] == 1
    assert context["record"]["played"] == 1
    assert context["next_match"]["opponent"] == "Chelsea"
    assert context["competition_name"] == "Premier League"
    assert not context["errors"]


def test_load_team_context_handles_missing_season(monkeypatch):
    monkeypatch.setattr(
        team_context,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: None,
    )
    monkeypatch.setattr(
        team_context,
        "list_competitions",
        lambda use_cache=True: [],
    )

    context = team_context.load_team_context(2, "2024/2025", "Arsenal")

    assert context["season_id"] is None
    assert context["matches_played"] == []
    assert context["team_summary"] is None
    assert "Season ID unavailable" in " ".join(context["errors"])


@pytest.mark.parametrize(
    "table_rows,expected_position",
    [
        (
            [
                {"team_name": "Arsenal", "team_season_points": 25, "team_season_goals": 20, "team_season_goals_against": 10},
                {"team_name": "Liverpool", "team_season_points": 25, "team_season_goals": 18, "team_season_goals_against": 12},
            ],
            1,
        ),
        (
            [
                {"team_name": "Arsenal", "team_season_points": 18, "team_season_goals": 12, "team_season_goals_against": 14},
                {"team_name": "Liverpool", "team_season_points": 22, "team_season_goals": 21, "team_season_goals_against": 11},
            ],
            2,
        ),
    ],
)
def test_sorting_logic(monkeypatch, table_rows, expected_position):
    monkeypatch.setattr(
        team_context,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )
    monkeypatch.setattr(
        team_context,
        "fetch_team_season_stats_data",
        lambda competition_id, season_id, use_cache=True: table_rows,
    )
    monkeypatch.setattr(
        team_context,
        "get_competition_players",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        team_context,
        "list_matches",
        lambda competition_id, season_id, team_name=None, use_cache=True: [],
    )
    monkeypatch.setattr(
        team_context,
        "list_competitions",
        lambda use_cache=True: [],
    )

    context = team_context.load_team_context(2, "2024/2025", "Arsenal")
    assert context["table_position"] == expected_position


def test_prompt_summary(monkeypatch):
    context = {
        "team_name": "Arsenal",
        "season_label": "2024/2025",
        "competition_id": 2,
        "table_position": 1,
        "table_size": 20,
        "team_summary": {"team_season_points": 28},
        "record": {"played": 10, "won": 8, "drawn": 1, "lost": 1, "goals_for": 24, "goals_against": 8, "goal_difference": 16},
        "next_match": {"date": "2024-09-01", "opponent": "Chelsea", "venue": "Away"},
    }

    summary = team_context.summarise_context_for_prompt(context, user_name="Scout", competition_name="Premier League")
    assert "User 'Scout'" in summary
    assert "Premier League" in summary
    assert "Table position: 1/20 with 28 points." in summary
    assert "Season record 8W-1D-1L" in summary


def test_list_teams_for_season(monkeypatch):
    monkeypatch.setattr(
        team_context,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: 317,
    )
    monkeypatch.setattr(
        team_context,
        "fetch_team_season_stats_data",
        lambda competition_id, season_id, use_cache=True: [
            {"team_name": "Arsenal"},
            {"team_name": "Liverpool"},
            {"team_name": "Arsenal"},
        ],
    )

    names = team_context.list_teams_for_season(2, "2024/2025")
    assert names == ["Arsenal", "Liverpool"]


def test_list_teams_for_season_missing(monkeypatch):
    monkeypatch.setattr(
        team_context,
        "season_id_for_label",
        lambda competition_id, season_label, use_cache=True: None,
    )
    with pytest.raises(RuntimeError):
        team_context.list_teams_for_season(2, "2024/2025")
