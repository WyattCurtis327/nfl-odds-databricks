"""Load nflverse schedule and match official game_id values."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from nfl_odds.nflverse_data import fetch_season_schedule
from nfl_odds.teams import to_abbr

ET = ZoneInfo("America/New_York")


def fetch_nflverse_schedule(season: int) -> pd.DataFrame:
    return fetch_season_schedule(season, game_types=("REG",))


def kickoff_et_date(commence_time: str) -> str:
    kickoff = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    return kickoff.astimezone(ET).date().isoformat()


def kickoff_et_datetime(commence_time: str) -> str:
    kickoff = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    return kickoff.astimezone(ET).strftime("%Y-%m-%d %H:%M")


def match_game_ids(
    odds_games: list[dict[str, Any]],
    schedule: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    """Map odds_api event id -> nflverse game metadata."""
    lookup: dict[str, dict[str, Any]] = {}

    for game in odds_games:
        away_abbr = to_abbr(game["away_team"])
        home_abbr = to_abbr(game["home_team"])
        gameday = kickoff_et_date(game["commence_time"])

        match = schedule[
            (schedule["away_team"] == away_abbr)
            & (schedule["home_team"] == home_abbr)
            & (schedule["gameday"] == gameday)
        ]
        if match.empty:
            match = schedule[
                (schedule["away_team"] == away_abbr) & (schedule["home_team"] == home_abbr)
            ]

        if match.empty:
            lookup[game["id"]] = {
                "game_id": None,
                "week": None,
                "away_abbr": away_abbr,
                "home_abbr": home_abbr,
                "gameday": gameday,
            }
            continue

        row = match.iloc[0]
        lookup[game["id"]] = {
            "game_id": row["game_id"],
            "week": int(row["week"]),
            "gsis": int(row["gsis"]) if pd.notna(row.get("gsis")) else None,
            "espn_id": int(row["espn"]) if pd.notna(row.get("espn")) else None,
            "away_abbr": away_abbr,
            "home_abbr": home_abbr,
            "gameday": gameday,
        }

    return lookup