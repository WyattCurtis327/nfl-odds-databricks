"""NFL odds ingestion and Databricks loading."""

from nfl_odds.core import (
    attach_game_ids,
    build_game_dimension,
    build_player_dimension,
    extract_pbp_player_roles,
)
from nfl_odds.fantasy import (
    build_fantasy_rankings,
    draft_log_frame,
    run_mock_draft,
    snake_pick_order,
)
from nfl_odds.simulation import (
    SimulationConfig,
    compute_team_scoring_profiles,
    filter_ungraded_predictions,
    grade_predictions,
    infer_latest_completed_week,
    infer_next_week,
    new_prediction_run_id,
    prepare_prediction_log,
    select_latest_prediction_run,
    simulate_weekly_picks,
    summarize_prediction_accuracy,
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
    "build_fantasy_rankings",
    "build_game_dimension",
    "build_player_dimension",
    "draft_log_frame",
    "extract_pbp_player_roles",
    "SimulationConfig",
    "compute_team_scoring_profiles",
    "filter_ungraded_predictions",
    "grade_predictions",
    "infer_latest_completed_week",
    "infer_next_week",
    "new_prediction_run_id",
    "prepare_prediction_log",
    "select_latest_prediction_run",
    "summarize_prediction_accuracy",
    "run_mock_draft",
    "simulate_weekly_picks",
    "snake_pick_order",
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