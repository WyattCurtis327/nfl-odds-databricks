import pandas as pd

from nfl_odds.nflverse_data import (
    fetch_play_by_play,
    fetch_rosters,
    fetch_season_schedule,
)


def test_fetch_play_by_play_filters_season_types(monkeypatch):
    sample = pd.DataFrame(
        {
            "season": [2025, 2025, 2025],
            "season_type": ["REG", "POST", "PRE"],
            "game_id": ["g1", "g2", "g3"],
            "play_id": [1, 2, 3],
        }
    )
    monkeypatch.setattr(
        "nfl_odds.nflverse_data.pd.read_parquet",
        lambda *_args, **_kwargs: sample,
    )

    result = fetch_play_by_play(2025, season_types=("REG", "POST"))
    assert set(result["season_type"]) == {"REG", "POST"}
    assert len(result) == 2


def test_fetch_rosters(monkeypatch):
    sample = pd.DataFrame(
        {
            "season": [2026, 2026],
            "team": ["SEA", "NE"],
            "full_name": ["Player A", "Player B"],
        }
    )
    monkeypatch.setattr(
        "nfl_odds.nflverse_data.pd.read_csv",
        lambda *_args, **_kwargs: sample,
    )

    result = fetch_rosters(2026)
    assert len(result) == 2


def test_fetch_season_schedule(monkeypatch):
    sample = pd.DataFrame(
        {
            "season": [2026, 2026, 2026],
            "game_type": ["REG", "REG", "POST"],
            "game_id": ["2026_01_NE_SEA", "2026_01_SF_LA", "2026_19_X_Y"],
            "week": [1, 1, 19],
        }
    )
    monkeypatch.setattr(
        "nfl_odds.nflverse_data.pd.read_csv",
        lambda *_args, **_kwargs: sample,
    )

    result = fetch_season_schedule(2026, game_types=("REG",))
    assert len(result) == 2
    assert set(result["game_type"]) == {"REG"}