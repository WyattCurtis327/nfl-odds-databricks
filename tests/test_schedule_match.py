import pandas as pd

from nfl_odds.schedule import match_game_ids


def test_match_game_ids_uses_kickoff_date(sample_odds_game, sample_schedule_df):
    lookup = match_game_ids([sample_odds_game], sample_schedule_df)
    meta = lookup[sample_odds_game["id"]]
    assert meta["game_id"] == "2026_01_NE_SEA"
    assert meta["week"] == 1


def test_match_game_ids_falls_back_to_team_only_when_date_differs(sample_odds_game):
    schedule = pd.DataFrame(
        [
            {
                "game_id": "2026_01_NE_SEA",
                "season": 2026,
                "game_type": "REG",
                "week": 1,
                "gameday": "2026-09-10",
                "away_team": "NE",
                "home_team": "SEA",
            }
        ]
    )
    lookup = match_game_ids([sample_odds_game], schedule)
    meta = lookup[sample_odds_game["id"]]
    assert meta["game_id"] == "2026_01_NE_SEA"


def test_match_game_ids_returns_null_when_no_match(sample_odds_game):
    schedule = pd.DataFrame(
        [
            {
                "game_id": "2026_01_DAL_NYG",
                "season": 2026,
                "game_type": "REG",
                "week": 1,
                "gameday": "2026-09-09",
                "away_team": "DAL",
                "home_team": "NYG",
            }
        ]
    )
    lookup = match_game_ids([sample_odds_game], schedule)
    meta = lookup[sample_odds_game["id"]]
    assert meta["game_id"] is None