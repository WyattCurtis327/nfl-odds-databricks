from nfl_odds.quality import assess_game_id_match_rate


def test_assess_game_id_match_rate_passes():
    rows = [
        {"game_id": "2026_01_NE_SEA"},
        {"game_id": "2026_01_DAL_NYG"},
    ]
    stats = assess_game_id_match_rate(rows, min_rate=0.9)
    assert stats["matched_games"] == 2
    assert stats["match_rate"] == 1.0
    assert stats["passed"] is True


def test_assess_game_id_match_rate_fails_below_threshold():
    rows = [
        {"game_id": "2026_01_NE_SEA"},
        {"game_id": None},
        {"game_id": None},
    ]
    stats = assess_game_id_match_rate(rows, min_rate=0.9)
    assert stats["matched_games"] == 1
    assert stats["unmatched_games"] == 2
    assert stats["passed"] is False