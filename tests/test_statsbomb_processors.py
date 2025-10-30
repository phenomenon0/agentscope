from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from agentspace.analytics import (
    DEFAULT_LEADERBOARD_GROUPS,
    build_player_leaderboards,
    events_to_dataframe,
    summarise_player_events,
    summarise_team_events,
)
from agentspace.services.statsbomb_tools import EventContext, MatchDataset, MatchDescriptor


@dataclass
class _DummyMatch:
    match_id: int
    home: str
    away: str

    def as_dict(self):
        return {
            "match_id": self.match_id,
            "match_date": "2024-08-12",
            "home_team": {"home_team_name": self.home},
            "away_team": {"away_team_name": self.away},
        }


def _event(event_id: str, event_type: str, team: str, player: str, extra: dict | None = None):
    base = {
        "id": event_id,
        "type": {"name": event_type},
        "team": {"name": team},
        "player": {"id": hash((team, player)) % 10_000, "name": player},
        "minute": 10,
        "second": 30.0,
        "period": 1,
        "location": [40.0, 40.0],
    }
    if extra:
        base.update(extra)
    return base


def _dataset(match_id=1):
    match = _DummyMatch(match_id, "Arsenal", "Manchester United")

    pass_event = _event(
        "evt-pass",
        "Pass",
        "Arsenal",
        "Martin Ødegaard",
        {
            "pass": {
                "end_location": [90.0, 45.0],
                "goal_assist": True,
                "assisted_shot_id": "shot-1",
            },
        },
    )

    shot_event = _event(
        "shot-1",
        "Shot",
        "Arsenal",
        "Gabriel Martinelli",
        {
            "shot": {
                "outcome": {"name": "Goal"},
                "xg": 0.32,
                "end_location": [120.0, 40.0],
            }
        },
    )

    pressure_event = _event("evt-pressure", "Pressure", "Arsenal", "Martin Ødegaard")

    carry_event = _event(
        "evt-carry",
        "Carry",
        "Arsenal",
        "Martin Ødegaard",
        {
            "carry": {
                "end_location": [100.0, 42.0],
                "distance": 20.0,
            }
        },
    )

    duel_event = _event(
        "evt-duel",
        "Duel",
        "Arsenal",
        "Declan Rice",
        {
            "duel": {"type": {"name": "Tackle"}, "outcome": {"name": "Won"}},
        },
    )

    interception_event = _event(
        "evt-interception",
        "Interception",
        "Arsenal",
        "Declan Rice",
        {
            "interception": {"outcome": {"name": "Won"}},
        },
    )

    recovery_event = _event("evt-recovery", "Ball Recovery", "Arsenal", "Declan Rice")

    events = [
        pass_event,
        shot_event,
        pressure_event,
        carry_event,
        duel_event,
        interception_event,
        recovery_event,
    ]

    descriptor = MatchDescriptor(match_id=match.match_id, competition_id=2, season_id=281, match=match.as_dict())
    contexts = [
        EventContext(event=e, match=match.as_dict(), home_score=0, away_score=0, score_state="level", elapsed_seconds=600)
        for e in events
    ]
    return MatchDataset(descriptor=descriptor, match=match.as_dict(), events=contexts)


def test_events_to_dataframe_and_player_summary():
    dataset = _dataset()
    df = events_to_dataframe(dataset)
    assert not df.empty
    assert "player_name" in df.columns
    assert df[df["event_type"] == "Pass"].iloc[0]["progressive_pass"]

    player_summary = summarise_player_events(df)
    assert not player_summary.empty

    odegaard = player_summary[player_summary["player_name"] == "Martin Ødegaard"].iloc[0]
    assert odegaard["passes_attempted"] == 1
    assert odegaard["passes_completed"] == 1
    assert odegaard["progressive_passes"] == 1
    assert odegaard["key_passes"] == 1
    assert odegaard["progressive_carries"] == 1
    assert odegaard["final_third_entries"] >= 1
    assert odegaard["assists"] == 1
    assert odegaard["pressures"] == 1

    martinelli = player_summary[player_summary["player_name"] == "Gabriel Martinelli"].iloc[0]
    assert martinelli["shots_total"] == 1
    assert martinelli["goals"] == 1
    assert abs(martinelli["xg"] - 0.32) < 1e-6

    rice = player_summary[player_summary["player_name"] == "Declan Rice"].iloc[0]
    assert rice["tackles_won"] == 1
    assert rice["interceptions"] == 1
    assert rice["ball_recoveries"] == 1


def test_team_summary_and_leaderboards():
    dataset = _dataset()
    df = events_to_dataframe(dataset)
    player_summary = summarise_player_events(df)
    team_summary = summarise_team_events(df)
    assert len(team_summary) == 1
    assert team_summary.iloc[0]["goals"] == 1

    leaderboards = build_player_leaderboards(player_summary, top_n=1)
    assert "shooting" in leaderboards
    shooting_table = leaderboards["shooting"]["goals"]
    assert shooting_table.iloc[0]["player_name"] == "Gabriel Martinelli"

    passing_table = leaderboards["passing"]["passes_completed"]
    assert passing_table.iloc[0]["player_name"] == "Martin Ødegaard"


def test_leaderboards_respect_minimums():
    dataset = _dataset()
    df = events_to_dataframe(dataset)
    player_summary = summarise_player_events(df)
    lb = build_player_leaderboards(player_summary, top_n=5, min_attempts=10)
    # pass_accuracy should be filtered out because only one attempt
    assert "pass_accuracy" not in lb.get("passing", {})
