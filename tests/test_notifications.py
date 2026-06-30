from unittest.mock import MagicMock, patch

import pandas as pd

from nfl_odds.notifications import format_predictions_email_html, send_email_sendgrid


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


@patch("nfl_odds.notifications.requests.post")
def test_send_email_sendgrid_posts_payload(mock_post):
    response = MagicMock()
    response.status_code = 202
    response.text = ""
    mock_post.return_value = response

    result = send_email_sendgrid(
        api_key="sg-test",
        to_email="user@example.com",
        subject="Test",
        html_content="<p>Hello</p>",
        from_email="sender@example.com",
    )

    assert result["status_code"] == 202
    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert payload["personalizations"][0]["to"][0]["email"] == "user@example.com"
    assert payload["from"]["email"] == "sender@example.com"


@patch("nfl_odds.notifications.requests.post")
def test_send_email_sendgrid_raises_on_error(mock_post):
    response = MagicMock()
    response.status_code = 403
    response.text = "Forbidden"
    mock_post.return_value = response

    try:
        send_email_sendgrid(
            api_key="sg-test",
            to_email="user@example.com",
            subject="Test",
            html_content="<p>Hello</p>",
            from_email="sender@example.com",
        )
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "403" in str(exc)

    assert raised