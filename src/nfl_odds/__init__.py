"""NFL odds ingestion and Databricks loading."""

from nfl_odds.core import (
    attach_game_ids,
    build_game_dimension,
    build_player_dimension,
    extract_pbp_player_roles,
)
from nfl_odds.fetch import fetch_nfl_odds
from nfl_odds.nflverse_data import (
    PbpNotAvailableError,
    fetch_play_by_play,
    fetch_play_by_play_for_elapsed_weeks,
    fetch_rosters,
    fetch_season_schedule,
    get_elapsed_weeks,
)
from nfl_odds.schedule import fetch_nflverse_schedule, match_game_ids
from nfl_odds.transform import flatten_odds, to_game_odds_rows

__all__ = [
    "attach_game_ids",
    "build_game_dimension",
    "build_player_dimension",
    "extract_pbp_player_roles",
    "fetch_nfl_odds",
    "fetch_nflverse_schedule",
    "PbpNotAvailableError",
    "fetch_play_by_play",
    "fetch_play_by_play_for_elapsed_weeks",
    "fetch_rosters",
    "fetch_season_schedule",
    "get_elapsed_weeks",
    "match_game_ids",
    "flatten_odds",
    "to_game_odds_rows",
]