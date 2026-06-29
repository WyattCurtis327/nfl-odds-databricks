"""Download reference datasets from nflverse."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

NFLVERSE_GAMES_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
NFLVERSE_PBP_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
)
NFLVERSE_ROSTER_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_{season}.csv"
)

DEFAULT_PBP_SEASON_TYPES = ("REG", "POST")
DEFAULT_SCHEDULE_GAME_TYPES = ("REG",)
ET = ZoneInfo("America/New_York")


class PbpNotAvailableError(FileNotFoundError):
    """Raised when nflverse has not published PBP for a season yet."""


def fetch_play_by_play(
    season: int,
    *,
    season_types: tuple[str, ...] | list[str] = DEFAULT_PBP_SEASON_TYPES,
) -> pd.DataFrame:
    """Load play-by-play for a season, filtered to regular/postseason."""
    url = NFLVERSE_PBP_URL.format(season=season)
    try:
        pbp = pd.read_parquet(url)
    except Exception as exc:
        if _is_missing_pbp_release(exc):
            raise PbpNotAvailableError(
                f"nflverse play-by-play not available for season {season}"
            ) from exc
        raise
    if season_types:
        pbp = pbp[pbp["season_type"].isin(season_types)].copy()
    return pbp


def _is_missing_pbp_release(exc: Exception) -> bool:
    message = str(exc).lower()
    return "404" in message or "not found" in message


def get_elapsed_weeks(
    schedule: pd.DataFrame,
    season: int,
    *,
    as_of: date | datetime | None = None,
    game_types: tuple[str, ...] | list[str] = ("REG",),
) -> list[int]:
    """Return regular-season weeks fully elapsed as of the given date."""
    if as_of is None:
        as_of_date = datetime.now(ET).date()
    elif isinstance(as_of, datetime):
        as_of_date = as_of.astimezone(ET).date()
    else:
        as_of_date = as_of

    reg = schedule[
        (schedule["season"] == season) & (schedule["game_type"].isin(game_types))
    ].copy()
    if reg.empty:
        return []

    elapsed: list[int] = []
    score_cols = {"home_score", "away_score"}.issubset(reg.columns)
    season_has_scores = (
        score_cols and reg["home_score"].notna().any() and reg["away_score"].notna().any()
    )

    for week, games in reg.groupby("week"):
        game_days = pd.to_datetime(games["gameday"]).dt.date
        week_complete_by_date = game_days.max() < as_of_date

        if season_has_scores:
            week_complete = (
                games["home_score"].notna().all() and games["away_score"].notna().all()
            )
        else:
            week_complete = week_complete_by_date

        if week_complete:
            elapsed.append(int(week))

    return sorted(elapsed)


def fetch_play_by_play_for_elapsed_weeks(
    season: int,
    *,
    as_of: date | datetime | None = None,
    season_types: tuple[str, ...] | list[str] = ("REG",),
    game_types: tuple[str, ...] | list[str] = ("REG",),
) -> tuple[pd.DataFrame, list[int]]:
    """Load current-season PBP limited to fully elapsed regular-season weeks."""
    schedule = fetch_season_schedule(season, game_types=game_types)
    elapsed_weeks = get_elapsed_weeks(schedule, season, as_of=as_of, game_types=game_types)
    if not elapsed_weeks:
        return pd.DataFrame(), []

    pbp = fetch_play_by_play(season, season_types=season_types)
    if pbp.empty:
        return pbp, elapsed_weeks

    filtered = pbp[
        (pbp["season"] == season)
        & (pbp["season_type"].isin(season_types))
        & (pbp["week"].isin(elapsed_weeks))
    ].copy()
    return filtered, elapsed_weeks


def fetch_rosters(season: int) -> pd.DataFrame:
    """Load season-level roster snapshot."""
    url = NFLVERSE_ROSTER_URL.format(season=season)
    return pd.read_csv(url)


def fetch_season_schedule(
    season: int,
    *,
    game_types: tuple[str, ...] | list[str] = DEFAULT_SCHEDULE_GAME_TYPES,
) -> pd.DataFrame:
    """Load schedule rows for a season."""
    schedule = pd.read_csv(NFLVERSE_GAMES_URL)
    filtered = schedule[schedule["season"] == season].copy()
    if game_types:
        filtered = filtered[filtered["game_type"].isin(game_types)]
    return filtered.reset_index(drop=True)