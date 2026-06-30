import pandas as pd

from nfl_odds.simulation import (
    grade_predictions,
    infer_latest_completed_week,
    prepare_prediction_log,
    resolve_spread_result,
    resolve_total_result,
    summarize_prediction_accuracy,
)


def test_resolve_spread_and_total_results():
    assert resolve_spread_result(17, 24, away_spread=3.5, home_spread=-3.5) == "home"
    assert resolve_spread_result(21, 24, away_spread=3.5, home_spread=-3.5) == "away"
    assert resolve_total_result(45, 44.5) == "over"
    assert resolve_total_result(40, 44.5) == "under"


def test_grade_predictions_marks_correct_picks():
    predictions = prepare_prediction_log(
        pd.DataFrame(
            [
                {
                    "game_id": "2026_01_NE_SEA",
                    "week": 1,
                    "away_abbr": "NE",
                    "home_abbr": "SEA",
                    "away_spread": 3.5,
                    "home_spread": -3.5,
                    "total_line": 44.5,
                    "spread_pick": "NE",
                    "total_pick": "OVER",
                    "spread_confidence": 0.61,
                    "total_confidence": 0.58,
                    "proj_away_score": 21.0,
                    "proj_home_score": 25.0,
                    "proj_total": 46.0,
                }
            ]
        ),
        season=2026,
        pbp_season=2025,
        prediction_run_id="run-1",
    )
    schedule = pd.DataFrame(
        [
            {
                "game_id": "2026_01_NE_SEA",
                "home_team": "SEA",
                "away_team": "NE",
                "home_score": 24.0,
                "away_score": 20.0,
            }
        ]
    )

    graded = grade_predictions(predictions, schedule)
    assert len(graded) == 1
    assert graded.iloc[0]["spread_correct"] == False
    assert graded.iloc[0]["actual_spread_result"] == "home"
    assert graded.iloc[0]["total_correct"] == False
    assert graded.iloc[0]["actual_total_result"] == "under"

    metrics = summarize_prediction_accuracy(graded)
    assert metrics["spread_accuracy"] == 0.0
    assert metrics["total_accuracy"] == 0.0


def test_infer_latest_completed_week():
    schedule = pd.DataFrame(
        [
            {"season": 2026, "week": 1, "home_score": 24.0, "away_score": 17.0},
            {"season": 2026, "week": 1, "home_score": 20.0, "away_score": 21.0},
            {"season": 2026, "week": 2, "home_score": None, "away_score": None},
        ]
    )
    assert infer_latest_completed_week(schedule, season=2026) == 1