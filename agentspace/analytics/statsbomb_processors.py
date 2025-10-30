"""Statistical processors for StatsBomb event data."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

import pandas as pd

from ..services.statsbomb_tools import MatchDataset

Number = Union[int, float]
PITCH_LENGTH = 120.0
PENALTY_AREA_X = 102.0
FINAL_THIRD_X = 80.0

TOUCH_EVENT_TYPES = {
    "Pass",
    "Carry",
    "Shot",
    "Dribble",
    "Ball Receipt*",
    "Ball Recovery",
}

SHOT_ON_TARGET_OUTCOMES = {
    "Goal",
    "Saved",
    "Saved To Post",
    "Saved To Woodwork",
    "Saved Off Target",
}

DEFAULT_LEADERBOARD_GROUPS: Mapping[str, Sequence[str]] = {
    "shooting": ("goals", "shots_total", "shots_on_target", "xg"),
    "chance_creation": ("assists", "key_passes", "xg_assisted", "final_third_entries"),
    "passing": ("passes_completed", "passes_attempted", "progressive_passes", "pass_accuracy"),
    "progression": (
        "progressive_actions",
        "progressive_passes",
        "progressive_carries",
        "penalty_area_entries",
    ),
    "defending": ("pressures", "tackles_won", "interceptions", "ball_recoveries"),
    "possession": ("touches_total", "touches_final_third", "touches_penalty_area"),
    "field_split": ("touches_def_third", "touches_mid_third", "touches_final_third"),
}


def _ensure_iterable(datasets: Union[MatchDataset, Sequence[MatchDataset]]) -> List[MatchDataset]:
    if isinstance(datasets, MatchDataset):
        return [datasets]
    return list(datasets)


def _player_id(event: dict) -> Optional[int]:
    player = event.get("player") or {}
    return player.get("id")


def _player_name(event: dict) -> Optional[str]:
    player = event.get("player") or {}
    return player.get("name")


def _team_name(event: dict) -> Optional[str]:
    team = event.get("team") or {}
    return team.get("name")


def _opponent_name(team_name: Optional[str], match: dict) -> Optional[str]:
    if not team_name or not match:
        return None
    home = match.get("home_team", {}).get("home_team_name")
    away = match.get("away_team", {}).get("away_team_name")
    if team_name == home:
        return away
    if team_name == away:
        return home
    return None


def _extract_location(event: dict, key: str) -> Tuple[Optional[float], Optional[float]]:
    if key == "start":
        value = event.get("location")
    elif "." in key:
        head, tail = key.split(".", 1)
        segment = event.get(head, {})
        value = segment.get(tail) if isinstance(segment, dict) else None
    else:
        segment = event.get(key, {})
        value = segment.get("end_location") if isinstance(segment, dict) else None
    if not value or len(value) < 2:
        return None, None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None, None


def _pass_end_location(event: dict) -> Tuple[Optional[float], Optional[float]]:
    return _extract_location(event, "pass")


def _carry_end_location(event: dict) -> Tuple[Optional[float], Optional[float]]:
    return _extract_location(event, "carry")


def _shot_end_location(event: dict) -> Tuple[Optional[float], Optional[float]]:
    return _extract_location(event, "shot")


def _distance_progress(start_x: Optional[float], end_x: Optional[float]) -> Optional[float]:
    if start_x is None or end_x is None:
        return None
    return end_x - start_x


def _is_progressive(start_x: Optional[float], end_x: Optional[float]) -> bool:
    if start_x is None or end_x is None:
        return False
    gain = end_x - start_x
    if gain <= 0:
        return False
    if start_x <= 40:
        return gain >= 30
    if start_x <= 60:
        return gain >= 20
    return gain >= 10


def _is_final_third_entry(start_x: Optional[float], end_x: Optional[float]) -> bool:
    if start_x is None or end_x is None:
        return False
    return start_x < FINAL_THIRD_X and end_x >= FINAL_THIRD_X


def _is_penalty_area_entry(start_x: Optional[float], end_x: Optional[float]) -> bool:
    if start_x is None or end_x is None:
        return False
    return start_x < PENALTY_AREA_X and end_x >= PENALTY_AREA_X


def _touch_zone(x: Optional[float]) -> Optional[str]:
    if x is None:
        return None
    if x < FINAL_THIRD_X / 2:
        return "defensive_third"
    if x < FINAL_THIRD_X:
        return "middle_third"
    return "final_third"


def _in_penalty_area(x: Optional[float], y: Optional[float]) -> bool:
    if x is None or y is None:
        return False
    return x >= PENALTY_AREA_X and 18.0 <= y <= 62.0


def events_to_dataframe(datasets: Union[MatchDataset, Sequence[MatchDataset]]) -> pd.DataFrame:
    """Flatten StatsBomb events from one or more matches into a DataFrame."""

    records: List[dict] = []
    for dataset in _ensure_iterable(datasets):
        match = dataset.match or {}
        match_id = dataset.descriptor.match_id
        competition_id = dataset.descriptor.competition_id
        season_id = dataset.descriptor.season_id
        match_date = match.get("match_date")
        for context in dataset.events:
            event = context.event
            start_x, start_y = _extract_location(event, "start")
            end_x, end_y = _pass_end_location(event)
            carry_end_x, carry_end_y = _carry_end_location(event)
            shot_end_x, shot_end_y = _shot_end_location(event)

            pass_data = event.get("pass", {})
            pass_recipient = pass_data.get("recipient", {}) if pass_data else {}
            carry_data = event.get("carry", {})
            shot_data = event.get("shot", {})
            duel_data = event.get("duel", {})
            interception_data = event.get("interception", {})
            dribble_data = event.get("dribble", {})

            pass_outcome = pass_data.get("outcome", {}).get("name") if pass_data else None
            if pass_data and pass_outcome is None:
                pass_outcome = "Complete"

            progressive_pass = _is_progressive(start_x, end_x)
            progressive_carry = _is_progressive(start_x, carry_end_x)
            final_third_entry = _is_final_third_entry(start_x, end_x) or _is_final_third_entry(start_x, carry_end_x)
            penalty_area_entry = _is_penalty_area_entry(start_x, end_x) or _is_penalty_area_entry(start_x, carry_end_x)

            pass_length = None
            if pass_data and start_x is not None and end_x is not None:
                pass_length = (pass_data.get("length") or _distance_progress(start_x, end_x))

            carry_length = None
            if carry_data and start_x is not None and carry_end_x is not None:
                carry_length = carry_data.get("distance") or _distance_progress(start_x, carry_end_x)

            progressive_pass_distance = _distance_progress(start_x, end_x) if progressive_pass else 0.0
            progressive_carry_distance = _distance_progress(start_x, carry_end_x) if progressive_carry else 0.0

            record = {
                "event_id": event.get("id"),
                "match_id": match_id,
                "competition_id": competition_id,
                "season_id": season_id,
                "match_date": match_date,
                "team": _team_name(event),
                "opponent": _opponent_name(_team_name(event), match),
                "player_id": _player_id(event),
                "player_name": _player_name(event),
                "event_type": event.get("type", {}).get("name"),
                "period": event.get("period"),
                "minute": event.get("minute"),
                "second": event.get("second"),
                "elapsed_seconds": context.elapsed_seconds,
                "location_x": start_x,
                "location_y": start_y,
                "pass_end_x": end_x,
                "pass_end_y": end_y,
                "carry_end_x": carry_end_x,
                "carry_end_y": carry_end_y,
                "shot_end_x": shot_end_x,
                "shot_end_y": shot_end_y,
                "pass_outcome": pass_outcome,
                "pass_length": pass_length,
                "pass_goal_assist": bool(pass_data.get("goal_assist")) if pass_data else False,
                "pass_assisted_shot_id": pass_data.get("assisted_shot_id") if pass_data else None,
                "pass_recipient_id": pass_recipient.get("id") if pass_recipient else None,
                "pass_recipient_name": pass_recipient.get("name") if pass_recipient else None,
                "progressive_pass": progressive_pass,
                "progressive_carry": progressive_carry,
                "final_third_entry": final_third_entry,
                "penalty_area_entry": penalty_area_entry,
                "carry_length": carry_length,
                "progressive_pass_distance": progressive_pass_distance,
                "progressive_carry_distance": progressive_carry_distance,
                "shot_outcome": shot_data.get("outcome", {}).get("name") if shot_data else None,
                "shot_xg": shot_data.get("xg") if shot_data else None,
                "shot_body_part": shot_data.get("body_part", {}).get("name") if shot_data else None,
                "pressured": bool(event.get("under_pressure")),
                "pressures": event.get("type", {}).get("name") == "Pressure",
                "duel_type": duel_data.get("type", {}).get("name") if duel_data else None,
                "duel_outcome": duel_data.get("outcome", {}).get("name") if duel_data else None,
                "interception_outcome": interception_data.get("outcome", {}).get("name") if interception_data else None,
                "dribble_outcome": dribble_data.get("outcome", {}).get("name") if dribble_data else None,
                "ball_recovery": event.get("type", {}).get("name") == "Ball Recovery",
                "possession_team": event.get("possession_team", {}).get("name"),
            }
            touch_zone = _touch_zone(start_x)
            record["touch_zone"] = touch_zone
            record["touch_in_box"] = _in_penalty_area(start_x, start_y)
            record["is_touch"] = record["event_type"] in TOUCH_EVENT_TYPES
            records.append(record)

    df = pd.DataFrame.from_records(records)
    if df.empty:
        return df

    shots = df[df["event_type"] == "Shot"][["event_id", "shot_xg"]].set_index("event_id")
    df["assisted_shot_xg"] = df["pass_assisted_shot_id"].map(shots["shot_xg"]) if not shots.empty else 0.0
    df.fillna({"assisted_shot_xg": 0.0}, inplace=True)
    return df


def _prepare_player_metrics(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["is_pass"] = df["event_type"] == "Pass"
    df["pass_completed"] = df["is_pass"] & (~df["pass_outcome"].fillna("Complete").ne("Complete"))
    df["is_shot"] = df["event_type"] == "Shot"
    df["is_goal"] = df["shot_outcome"].fillna("").str.lower() == "goal"
    df["shot_on_target"] = df["shot_outcome"].isin(SHOT_ON_TARGET_OUTCOMES)
    df["is_key_pass"] = df["pass_assisted_shot_id"].notna()
    df["is_assist"] = df["pass_goal_assist"]
    df["is_carry"] = df["event_type"] == "Carry"
    df["is_pressure"] = df["event_type"] == "Pressure"
    df["is_interception"] = df["event_type"] == "Interception"
    df["interception_success"] = df["is_interception"] & df["interception_outcome"].fillna("Successful").ne("Lost")
    df["is_duel_tackle"] = (df["event_type"] == "Duel") & (df["duel_type"] == "Tackle")
    df["tackle_won"] = df["is_duel_tackle"] & df["duel_outcome"].fillna("Won").isin({"Won", "Success", "Won Tackle"})
    df["dribble"] = df["event_type"] == "Dribble"
    df["dribble_completed"] = df["dribble"] & df["dribble_outcome"].fillna("Complete").eq("Complete")
    df["ball_recovery_event"] = df["event_type"] == "Ball Recovery"
    df["progressive_pass"] = df["progressive_pass"].fillna(False)
    df["progressive_carry"] = df["progressive_carry"].fillna(False)
    df["final_third_entry"] = df["final_third_entry"].fillna(False)
    df["penalty_area_entry"] = df["penalty_area_entry"].fillna(False)
    df["touch_in_box"] = df["touch_in_box"].fillna(False)
    df["is_touch"] = df["is_touch"].fillna(False)

    df["progressive_action"] = df["progressive_pass"] | df["progressive_carry"]
    df["touches_def_third"] = df["is_touch"] & df["touch_zone"].eq("defensive_third")
    df["touches_mid_third"] = df["is_touch"] & df["touch_zone"].eq("middle_third")
    df["touches_final_third"] = df["is_touch"] & df["touch_zone"].eq("final_third")
    df["touches_penalty_area"] = df["is_touch"] & df["touch_in_box"]

    if "progressive_pass_distance" not in df.columns:
        df["progressive_pass_distance"] = 0.0
    else:
        df["progressive_pass_distance"] = df["progressive_pass_distance"].fillna(0.0)
    if "progressive_carry_distance" not in df.columns:
        df["progressive_carry_distance"] = 0.0
    else:
        df["progressive_carry_distance"] = df["progressive_carry_distance"].fillna(0.0)
    return df


def summarise_player_events(
    events_df: pd.DataFrame,
    group_columns: Sequence[str] = ("match_id", "player_id", "player_name", "team"),
) -> pd.DataFrame:
    """Aggregate event DataFrame into per-player match summaries."""

    if events_df.empty:
        return pd.DataFrame(
            columns=list(group_columns)
            + [
                "passes_attempted",
                "passes_completed",
                "pass_accuracy",
                "progressive_passes",
                "progressive_pass_distance",
                "key_passes",
                "xg_assisted",
                "assists",
                "shots_total",
                "shots_on_target",
                "goals",
                "xg",
                "pressures",
                "tackles_won",
                "interceptions",
                "ball_recoveries",
                "dribbles_completed",
                "carries",
                "progressive_carries",
                "progressive_carry_distance",
                "progressive_actions",
                "final_third_entries",
                "penalty_area_entries",
                "touches_total",
                "touches_def_third",
                "touches_mid_third",
                "touches_final_third",
                "touches_penalty_area",
            ]
        )

    df = _prepare_player_metrics(events_df)

    agg_map = {
        "passes_attempted": ("is_pass", "sum"),
        "passes_completed": ("pass_completed", "sum"),
        "progressive_passes": ("progressive_pass", "sum"),
        "progressive_pass_distance": ("progressive_pass_distance", "sum"),
        "key_passes": ("is_key_pass", "sum"),
        "xg_assisted": ("assisted_shot_xg", "sum"),
        "assists": ("is_assist", "sum"),
        "shots_total": ("is_shot", "sum"),
        "shots_on_target": ("shot_on_target", "sum"),
        "goals": ("is_goal", "sum"),
        "xg": ("shot_xg", "sum"),
        "pressures": ("is_pressure", "sum"),
        "tackles_won": ("tackle_won", "sum"),
        "interceptions": ("interception_success", "sum"),
        "ball_recoveries": ("ball_recovery_event", "sum"),
        "dribbles_completed": ("dribble_completed", "sum"),
        "carries": ("is_carry", "sum"),
        "progressive_carries": ("progressive_carry", "sum"),
        "progressive_carry_distance": ("progressive_carry_distance", "sum"),
        "progressive_actions": ("progressive_action", "sum"),
        "final_third_entries": ("final_third_entry", "sum"),
        "penalty_area_entries": ("penalty_area_entry", "sum"),
        "touches_total": ("is_touch", "sum"),
        "touches_def_third": ("touches_def_third", "sum"),
        "touches_mid_third": ("touches_mid_third", "sum"),
        "touches_final_third": ("touches_final_third", "sum"),
        "touches_penalty_area": ("touches_penalty_area", "sum"),
        "match_date": ("match_date", "first"),
        "opponent": ("opponent", "first"),
    }

    group_cols = list(group_columns)
    available_cols = [col for col in df.columns if any(col == spec[0] for spec in agg_map.values())]
    agg_spec = {key: agg_map[key] for key in agg_map if agg_map[key][0] in available_cols or key in {"match_date", "opponent"}}

    grouped = df.groupby(group_cols, dropna=False).agg(**agg_spec).reset_index()
    grouped["passes_attempted"] = grouped["passes_attempted"].astype(float)
    grouped["passes_completed"] = grouped["passes_completed"].astype(float)
    grouped["pass_accuracy"] = grouped.apply(
        lambda row: row["passes_completed"] / row["passes_attempted"] if row["passes_attempted"] else 0.0,
        axis=1,
    )
    grouped["shots_total"] = grouped["shots_total"].astype(float)
    grouped["shots_on_target"] = grouped["shots_on_target"].astype(float)
    grouped["shot_accuracy"] = grouped.apply(
        lambda row: row["shots_on_target"] / row["shots_total"] if row["shots_total"] else 0.0,
        axis=1,
    )
    return grouped.fillna(0)


def summarise_team_events(events_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate event DataFrame into per-team match summaries."""

    player_summary = summarise_player_events(events_df, group_columns=("match_id", "team"))
    if player_summary.empty:
        return player_summary

    team_summary = (
        player_summary.groupby(["match_id", "team", "match_date", "opponent"], dropna=False)
        .sum(numeric_only=True)
        .reset_index()
    )
    return team_summary


def build_player_leaderboards(
    player_summary: pd.DataFrame,
    groups: Mapping[str, Sequence[str]] = DEFAULT_LEADERBOARD_GROUPS,
    top_n: int = 5,
    min_attempts: int = 20,
) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Generate leaderboards per statistical category from player summaries."""

    if player_summary.empty:
        return {}

    leaderboards: Dict[str, Dict[str, pd.DataFrame]] = {}
    base = player_summary.copy()
    base = base.sort_values("match_date", ascending=False)

    for category, metrics in groups.items():
        metric_tables: Dict[str, pd.DataFrame] = {}
        for metric in metrics:
            if metric not in base.columns:
                continue
            table = base[["player_name", "team", metric]].copy()
            if metric == "pass_accuracy":
                table = table[base["passes_attempted"] >= min_attempts]
            if metric == "shot_accuracy":
                table = table[base["shots_total"] >= max(1, min_attempts / 4)]
            if table.empty:
                continue
            table = table.sort_values(metric, ascending=False).head(top_n)
            metric_tables[metric] = table.reset_index(drop=True)
        if metric_tables:
            leaderboards[category] = metric_tables
    return leaderboards
