from unittest.mock import MagicMock, patch

import pytest

from nfl_odds.fetch import OddsApiError, fetch_nfl_odds


def test_fetch_nfl_odds_requires_api_key(monkeypatch):
    monkeypatch.delenv("odds_api_key", raising=False)
    with pytest.raises(OddsApiError, match="Missing odds_api_key"):
        fetch_nfl_odds(api_key="")


@patch("nfl_odds.fetch.requests.get")
def test_fetch_nfl_odds_returns_payload_and_headers(mock_get):
    response = MagicMock()
    response.ok = True
    response.json.return_value = [{"id": "game-1"}]
    response.headers = {
        "x-requests-remaining": "99",
        "x-requests-used": "1",
        "x-requests-last": "1",
    }
    mock_get.return_value = response

    games, headers = fetch_nfl_odds(api_key="test-key")

    assert games == [{"id": "game-1"}]
    assert headers["x-requests-remaining"] == "99"
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["params"]["apiKey"] == "test-key"


@patch("nfl_odds.fetch.requests.get")
def test_fetch_nfl_odds_raises_on_http_error(mock_get):
    response = MagicMock()
    response.ok = False
    response.status_code = 401
    response.text = "Unauthorized"
    mock_get.return_value = response

    with pytest.raises(OddsApiError, match="401"):
        fetch_nfl_odds(api_key="bad-key")