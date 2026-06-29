import pandas as pd
import pytest


@pytest.fixture
def sample_odds_game():
    return {
        "id": "8c94552d022acec4a0458d70c19d3da9",
        "sport_key": "americanfootball_nfl",
        "commence_time": "2026-09-10T00:15:00Z",
        "home_team": "Seattle Seahawks",
        "away_team": "New England Patriots",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "last_update": "2026-06-29T04:44:52Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "New England Patriots", "price": 164},
                            {"name": "Seattle Seahawks", "price": -198},
                        ],
                    },
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "New England Patriots", "price": -110, "point": 3.5},
                            {"name": "Seattle Seahawks", "price": -110, "point": -3.5},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": -110, "point": 44.5},
                            {"name": "Under", "price": -110, "point": 44.5},
                        ],
                    },
                ],
            }
        ],
    }


@pytest.fixture
def sample_schedule_df():
    return pd.DataFrame(
        [
            {
                "game_id": "2026_01_NE_SEA",
                "season": 2026,
                "game_type": "REG",
                "week": 1,
                "gameday": "2026-09-09",
                "away_team": "NE",
                "home_team": "SEA",
            }
        ]
    )