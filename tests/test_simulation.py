import pandas as pd

from nfl_odds.simulation import (
    SimulationConfig,
    calibrate_expected_scores_to_market,
    compute_team_scoring_profiles,
    expected_matchup_scores,
    infer_next_week,
    simulate_game_outcomes,
    simulate_weekly_picks,
)


def _sample_pbp() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": "2025_01_NE_SEA",
                "home_team": "SEA",
                "away_team": "NE",
                "total_home_score": 24.0,
                "total_away_score": 17.0,
            },
            {
                "game_id": "2025_02_NE_NYJ",
                "home_team": "NYJ",
                "away_team": "NE",
                "total_home_score": 10.0,
                "total_away_score": 27.0,
            },
            {
                "game_id": "2025_02_SEA_LA",
                "home_team": "LA",
                "away_team": "SEA",
                "total_home_score": 30.0,
                "total_away_score": 20.0,
            },
        ]
    )


def _sample_odds_week1() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": "2026_01_NE_SEA",
                "week": 1,
                "gameday": "2026-09-09",
                "kickoff_et": "2026-09-09 20:15",
                "away_abbr": "NE",
                "home_abbr": "SEA",
                "away_spread": 3.5,
                "home_spread": -3.5,
                "total_line": 44.5,
                "bookmaker": "DraftKings",
            }
        ]
    )


def test_compute_team_scoring_profiles():
    profiles = compute_team_scoring_profiles(_sample_pbp())
    assert set(profiles["team"]) == {"NE", "SEA", "NYJ", "LA"}
    assert profiles.loc[profiles["team"] == "NE", "points_for_mean"].iloc[0] == 22.0


def test_calibrate_expected_scores_to_market():
    home_mu, away_mu = calibrate_expected_scores_to_market(
        24.0,
        20.0,
        home_spread=-3.5,
        total_line=44.5,
        market_blend=0.5,
    )
    assert 20.0 < home_mu < 26.0
    assert 18.0 < away_mu < 24.0


def test_simulate_game_outcomes_returns_probabilities():
    sim = simulate_game_outcomes(
        24.0,
        21.0,
        8.0,
        8.0,
        home_spread=-3.5,
        away_spread=3.5,
        total_line=44.5,
        config=SimulationConfig(n_simulations=5000, random_seed=7),
    )
    assert 0.0 < sim["away_cover_pct"] < 1.0
    assert 0.0 < sim["over_pct"] < 1.0
    assert abs(sim["away_cover_pct"] + sim["home_cover_pct"] - 1.0) < 0.02


def test_simulate_weekly_picks_for_week():
    profiles = compute_team_scoring_profiles(_sample_pbp())
    picks = simulate_weekly_picks(
        _sample_odds_week1(),
        profiles,
        week=1,
        config=SimulationConfig(n_simulations=3000, random_seed=3),
    )
    assert len(picks) == 1
    assert picks.iloc[0]["spread_pick"] in {"NE", "SEA"}
    assert picks.iloc[0]["total_pick"] in {"OVER", "UNDER"}


def test_infer_next_week():
    schedule = pd.DataFrame(
        [
            {"season": 2026, "week": 1, "home_score": None, "away_score": None},
            {"season": 2026, "week": 2, "home_score": None, "away_score": None},
        ]
    )
    assert infer_next_week(schedule, season=2026) == 1