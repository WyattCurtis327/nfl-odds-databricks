import pandas as pd

from nfl_odds.core import (
    attach_game_ids,
    build_game_dimension,
    build_player_dimension,
    extract_pbp_player_roles,
)


def test_build_player_dimension_uses_gsis_id_not_name():
    rosters = pd.DataFrame(
        [
            {
                "gsis_id": "00-0036322",
                "full_name": "Justin Jefferson",
                "team": "MIN",
                "position": "WR",
                "jersey_number": 18,
                "status": "ACT",
                "espn_id": 1.0,
                "season": 2026,
                "week": 1,
            },
            {
                "gsis_id": "00-0039999",
                "full_name": "Justin Jefferson",
                "team": "DAL",
                "position": "CB",
                "jersey_number": 30,
                "status": "ACT",
                "espn_id": 2.0,
                "season": 2026,
                "week": 1,
            },
        ]
    )

    players = build_player_dimension(rosters)
    assert len(players) == 2
    assert players["player_id"].is_unique
    assert players["name_collision"].all()
    assert "Justin Jefferson (MIN)" in players["player_label"].values
    assert "Justin Jefferson (DAL)" in players["player_label"].values


def test_build_game_dimension_dedupes_by_game_id():
    schedule = pd.DataFrame(
        [
            {
                "game_id": "2026_01_NE_SEA",
                "season": 2026,
                "game_type": "REG",
                "week": 1,
                "gameday": "2026-09-09",
                "away_team": "NE",
                "home_team": "SEA",
            },
            {
                "game_id": "2026_01_NE_SEA",
                "season": 2026,
                "game_type": "REG",
                "week": 1,
                "gameday": "2026-09-09",
                "away_team": "NE",
                "home_team": "SEA",
            },
        ]
    )

    games = build_game_dimension(schedule)
    assert len(games) == 1
    assert games.iloc[0]["game_id"] == "2026_01_NE_SEA"


def test_attach_game_ids(sample_odds_game, sample_schedule_df):
    rows = [{"odds_api_id": sample_odds_game["id"], "market": "h2h"}]
    enriched = attach_game_ids(rows, [sample_odds_game], sample_schedule_df)
    assert enriched[0]["game_id"] == "2026_01_NE_SEA"
    assert enriched[0]["away_abbr"] == "NE"


def test_extract_pbp_player_roles_prefers_player_id():
    pbp = pd.DataFrame(
        [
            {
                "game_id": "2025_01_ARI_NO",
                "play_id": 1.0,
                "season": 2025,
                "season_type": "REG",
                "week": 1,
                "passer_player_id": "00-0035228",
                "passer_player_name": "K.Murray",
                "rusher_player_id": "00-0035228",
                "rusher_player_name": "K.Murray",
            }
        ]
    )

    roles = extract_pbp_player_roles(pbp)
    assert set(roles["role"]) == {"passer", "rusher"}
    assert (roles["player_id"] == "00-0035228").all()
    assert roles["player_name"].iloc[0] == "K.Murray"