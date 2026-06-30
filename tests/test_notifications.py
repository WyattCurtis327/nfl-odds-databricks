import pandas as pd

from nfl_odds.notifications import format_predictions_email_html


def test_format_predictions_email_html_includes_games():
    picks = pd.DataFrame(
        [
            {
                "away_abbr": "NE",
                "home_abbr": "SEA",
                "away_spread": 3.5,
                "total_line": 44.5,
                "spread_pick": "SEA",
                "spread_confidence": 0.509,
                "total_pick": "OVER",
                "total_confidence": 0.567,
                "proj_away_score": 21.29,
                "proj_home_score": 25.32,
            }
        ]
    )
    html = format_predictions_email_html(
        picks,
        season=2026,
        week=1,
        prediction_run_id="run-123",
        run_page_url="https://example.com/run/1",
    )
    assert "NE" in html
    assert "SEA" in html
    assert "run-123" in html
    assert "https://example.com/run/1" in html