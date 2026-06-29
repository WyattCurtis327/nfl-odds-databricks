"""Fetch NFL odds from The Odds API."""

from __future__ import annotations

import os
from typing import Any

import requests

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
DEFAULT_MARKETS = "h2h,spreads,totals"
DEFAULT_REGIONS = "us"


class OddsApiError(RuntimeError):
    pass


def fetch_nfl_odds(
    api_key: str | None = None,
    *,
    regions: str = DEFAULT_REGIONS,
    markets: str = DEFAULT_MARKETS,
    odds_format: str = "american",
    timeout: int = 30,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Return upcoming NFL odds and response headers."""
    key = (api_key or os.environ.get("odds_api_key") or "").strip()
    if not key:
        raise OddsApiError("Missing odds_api_key environment variable or api_key argument")

    url = f"{ODDS_API_BASE}/sports/americanfootball_nfl/odds"
    params = {
        "apiKey": key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
    }
    response = requests.get(url, params=params, timeout=timeout)
    if not response.ok:
        raise OddsApiError(f"Odds API request failed ({response.status_code}): {response.text}")

    headers = {
        "x-requests-remaining": response.headers.get("x-requests-remaining", ""),
        "x-requests-used": response.headers.get("x-requests-used", ""),
        "x-requests-last": response.headers.get("x-requests-last", ""),
    }
    return response.json(), headers