from datetime import date

import pandas as pd
import pytest

from nfl_odds.nflverse_data import (
    PbpNotAvailableError,
    fetch_play_by_play_for_elapsed_weeks,
    get_elapsed_weeks,
)


def test_get_elapsed_weeks_uses_scores_when_available():
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_type": "REG",
                "week": 1,
                "gameday": "2026-09-13",
                "home_score": 24.0,
                "away_score": 17.0,
            },
            {
                "season": 2026,
                "game_type": "REG",
                "week": 2,
                "gameday": "2026-09-20",
                "home_score": None,
                "away_score": None,
            },
        ]
    )

    elapsed = get_elapsed_weeks(schedule, 2026, as_of=date(2026, 9, 21))
    assert elapsed == [1]


def test_get_elapsed_weeks_uses_gameday_before_scores_exist():
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_type": "REG",
                "week": 1,
                "gameday": "2026-09-13",
            },
            {
                "season": 2026,
                "game_type": "REG",
                "week": 2,
                "gameday": "2026-09-20",
            },
        ]
    )

    elapsed = get_elapsed_weeks(schedule, 2026, as_of=date(2026, 9, 14))
    assert elapsed == [1]


def test_fetch_play_by_play_for_elapsed_weeks(monkeypatch):
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_type": "REG",
                "week": 1,
                "gameday": "2026-09-13",
                "home_score": 21.0,
                "away_score": 14.0,
            }
        ]
    )
    pbp = pd.DataFrame(
        [
            {
                "season": 2026,
                "season_type": "REG",
                "week": 1,
                "game_id": "2026_01_NE_SEA",
                "play_id": 1,
            },
            {
                "season": 2026,
                "season_type": "REG",
                "week": 2,
                "game_id": "2026_02_X_Y",
                "play_id": 2,
            },
        ]
    )

    monkeypatch.setattr(
        "nfl_odds.nflverse_data.fetch_season_schedule",
        lambda *_args, **_kwargs: schedule,
    )
    monkeypatch.setattr(
        "nfl_odds.nflverse_data.fetch_play_by_play",
        lambda *_args, **_kwargs: pbp,
    )

    result, weeks = fetch_play_by_play_for_elapsed_weeks(2026, as_of=date(2026, 9, 14))
    assert weeks == [1]
    assert len(result) == 1
    assert result.iloc[0]["game_id"] == "2026_01_NE_SEA"


def test_fetch_play_by_play_raises_when_release_missing(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise OSError("HTTP Error 404: Not Found")

    monkeypatch.setattr("nfl_odds.nflverse_data.pd.read_parquet", _raise)

    with pytest.raises(PbpNotAvailableError):
        from nfl_odds.nflverse_data import fetch_play_by_play

        fetch_play_by_play(2026)