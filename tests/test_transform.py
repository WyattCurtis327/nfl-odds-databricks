from nfl_odds.schedule import kickoff_et_date, match_game_ids
from nfl_odds.teams import to_abbr
from nfl_odds.transform import flatten_odds, to_game_odds_rows


def test_team_mapping():
    assert to_abbr("Seattle Seahawks") == "SEA"
    assert to_abbr("Los Angeles Rams") == "LA"


def test_kickoff_et_date():
    assert kickoff_et_date("2026-09-10T00:15:00Z") == "2026-09-09"


def test_flatten_and_match(sample_odds_game, sample_schedule_df):
    rows = flatten_odds([sample_odds_game])
    assert len(rows) == 6  # 3 markets x 2 outcomes

    lookup = match_game_ids([sample_odds_game], sample_schedule_df)
    assert lookup[sample_odds_game["id"]]["game_id"] == "2026_01_NE_SEA"

    game_rows = to_game_odds_rows([sample_odds_game], sample_schedule_df)
    assert game_rows[0]["game_id"] == "2026_01_NE_SEA"
    assert game_rows[0]["away_ml"] == 164