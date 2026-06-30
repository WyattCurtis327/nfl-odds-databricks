import pandas as pd
import pytest

from nfl_odds.fantasy import (
    ROSTER_SLOTS,
    build_fantasy_rankings,
    draft_log_frame,
    run_mock_draft,
    snake_pick_order,
)


def _sample_pbp() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": "2025_01_ARI_NO",
                "home_team": "ARI",
                "away_team": "NO",
                "defteam": "NO",
                "posteam": "ARI",
                "passer_player_id": "00-0035228",
                "passer_player_name": "K.Murray",
                "passing_yards": 25.0,
                "pass_touchdown": 1.0,
                "interception": 0.0,
                "rusher_player_id": "00-0033553",
                "rusher_player_name": "J.Conner",
                "rushing_yards": 50.0,
                "rush_touchdown": 1.0,
                "fumble_lost": 0.0,
                "receiver_player_id": "00-0037744",
                "receiver_player_name": "T.McBride",
                "receiving_yards": 40.0,
                "complete_pass": 1.0,
                "kicker_player_id": "00-0031111",
                "kicker_player_name": "C.Ryland",
                "field_goal_result": "made",
                "extra_point_result": "good",
                "sack": 1.0,
                "total_home_score": 20.0,
                "total_away_score": 10.0,
            },
            {
                "game_id": "2025_01_ARI_NO",
                "home_team": "ARI",
                "away_team": "NO",
                "defteam": "ARI",
                "posteam": "NO",
                "passer_player_id": "00-0039376",
                "passer_player_name": "S.Rattler",
                "passing_yards": 10.0,
                "pass_touchdown": 0.0,
                "interception": 1.0,
                "rusher_player_id": "00-0033906",
                "rusher_player_name": "A.Kamara",
                "rushing_yards": 20.0,
                "rush_touchdown": 0.0,
                "fumble_lost": 1.0,
                "receiver_player_id": "00-0037239",
                "receiver_player_name": "C.Olave",
                "receiving_yards": 15.0,
                "complete_pass": 1.0,
                "sack": 0.0,
                "total_home_score": 20.0,
                "total_away_score": 10.0,
            },
        ]
    )


def _sample_rosters() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "gsis_id": "00-0035228",
                "full_name": "Kyler Murray",
                "team": "ARI",
                "position": "QB",
                "season": 2026,
                "week": 1,
            },
            {
                "gsis_id": "00-0033553",
                "full_name": "James Conner",
                "team": "ARI",
                "position": "RB",
                "season": 2026,
                "week": 1,
            },
            {
                "gsis_id": "00-0037744",
                "full_name": "Trey McBride",
                "team": "ARI",
                "position": "TE",
                "season": 2026,
                "week": 1,
            },
            {
                "gsis_id": "00-0039376",
                "full_name": "Spencer Rattler",
                "team": "NO",
                "position": "QB",
                "season": 2026,
                "week": 1,
            },
            {
                "gsis_id": "00-0033906",
                "full_name": "Alvin Kamara",
                "team": "NO",
                "position": "RB",
                "season": 2026,
                "week": 1,
            },
            {
                "gsis_id": "00-0037239",
                "full_name": "Chris Olave",
                "team": "NO",
                "position": "WR",
                "season": 2026,
                "week": 1,
            },
            {
                "gsis_id": "00-0031111",
                "full_name": "Chad Ryland",
                "team": "ARI",
                "position": "K",
                "season": 2026,
                "week": 1,
            },
        ]
    )


def test_snake_pick_order_reverses_each_round():
    order = snake_pick_order(team_count=4, rounds=2)
    assert order == [1, 2, 3, 4, 4, 3, 2, 1]


def test_build_fantasy_rankings_assigns_positions():
    rankings = build_fantasy_rankings(_sample_pbp(), _sample_rosters())
    assert not rankings.empty
    assert set(rankings["position"].dropna()) <= {"QB", "RB", "WR", "TE", "K", "DEF"}
    assert (rankings["player_id"] == "DEF-ARI").any()
    assert (rankings["player_id"] == "00-0033553").any()


def test_run_mock_draft_fills_user_roster():
    rankings = build_fantasy_rankings(_sample_pbp(), _sample_rosters())
    expanded = []
    for position, count in [("QB", 4), ("RB", 8), ("WR", 12), ("TE", 4), ("K", 4), ("DEF", 4)]:
        pos_rows = rankings[rankings["position"] == position]
        template = pos_rows.iloc[0] if not pos_rows.empty else rankings.iloc[0]
        for idx in range(count):
            row = template.copy()
            row["player_id"] = f"{position}-{idx}"
            row["player_name"] = f"{position} Player {idx}"
            row["position"] = position
            row["points_per_game"] = float(template["points_per_game"]) - idx * 0.1
            expanded.append(row)

    pool = pd.DataFrame(expanded)
    picks, rosters = run_mock_draft(pool, user_draft_position=2, team_count=3)
    user = rosters[2]
    assert len(user.picks) == sum(ROSTER_SLOTS.values())
    assert any(p.is_user for p in picks)
    assert draft_log_frame(picks)["user_pick"].any()


def test_run_mock_draft_rejects_invalid_slot():
    rankings = build_fantasy_rankings(_sample_pbp(), _sample_rosters())
    with pytest.raises(ValueError):
        run_mock_draft(rankings, user_draft_position=13)