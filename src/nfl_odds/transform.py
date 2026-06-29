"""Flatten Odds API payloads into tabular rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from nfl_odds.schedule import kickoff_et_datetime, match_game_ids


def flatten_odds(
    odds_games: list[dict[str, Any]],
    *,
    schedule_df=None,
    ingested_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Explode bookmaker markets into one row per outcome."""
    from nfl_odds.core import attach_game_ids

    ingested = ingested_at or datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []

    for game in odds_games:
        for bookmaker in game.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                for outcome in market.get("outcomes", []):
                    rows.append(
                        {
                            "odds_api_id": game["id"],
                            "commence_time": game["commence_time"],
                            "away_team": game["away_team"],
                            "home_team": game["home_team"],
                            "bookmaker_key": bookmaker["key"],
                            "bookmaker_title": bookmaker["title"],
                            "market": market["key"],
                            "outcome_name": outcome["name"],
                            "price": outcome.get("price"),
                            "point": outcome.get("point"),
                            "bookmaker_last_update": bookmaker.get("last_update"),
                            "market_last_update": market.get("last_update"),
                            "ingested_at": ingested.isoformat(),
                        }
                    )

    if schedule_df is not None:
        rows = attach_game_ids(rows, odds_games, schedule_df)
    return rows


def to_game_odds_rows(
    odds_games: list[dict[str, Any]],
    schedule_df,
    *,
    preferred_bookmaker: str = "draftkings",
    ingested_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Build one wide row per game using a preferred bookmaker."""
    ingested = ingested_at or datetime.now(timezone.utc)
    game_lookup = match_game_ids(odds_games, schedule_df)
    rows: list[dict[str, Any]] = []

    for game in odds_games:
        meta = game_lookup[game["id"]]
        bookmaker = next(
            (b for b in game.get("bookmakers", []) if b["key"] == preferred_bookmaker),
            game["bookmakers"][0] if game.get("bookmakers") else None,
        )
        if not bookmaker:
            continue

        h2h = next((m for m in bookmaker["markets"] if m["key"] == "h2h"), None)
        spreads = next((m for m in bookmaker["markets"] if m["key"] == "spreads"), None)
        totals = next((m for m in bookmaker["markets"] if m["key"] == "totals"), None)

        def outcome(market, team_name: str):
            if not market:
                return None, None
            hit = next((o for o in market["outcomes"] if o["name"] == team_name), None)
            if not hit:
                return None, None
            return hit.get("point"), hit.get("price")

        away_spread, away_spread_odds = outcome(spreads, game["away_team"])
        home_spread, home_spread_odds = outcome(spreads, game["home_team"])
        _, away_ml = outcome(h2h, game["away_team"])
        _, home_ml = outcome(h2h, game["home_team"])
        over = next((o for o in (totals or {}).get("outcomes", []) if o["name"] == "Over"), None)
        under = next((o for o in (totals or {}).get("outcomes", []) if o["name"] == "Under"), None)

        rows.append(
            {
                "game_id": meta["game_id"],
                "week": meta["week"],
                "gsis": meta.get("gsis"),
                "espn_id": meta.get("espn_id"),
                "odds_api_id": game["id"],
                "gameday": meta["gameday"],
                "kickoff_et": kickoff_et_datetime(game["commence_time"]),
                "away_team": game["away_team"],
                "home_team": game["home_team"],
                "away_abbr": meta["away_abbr"],
                "home_abbr": meta["home_abbr"],
                "away_ml": away_ml,
                "home_ml": home_ml,
                "away_spread": away_spread,
                "away_spread_odds": away_spread_odds,
                "home_spread": home_spread,
                "home_spread_odds": home_spread_odds,
                "total_line": over.get("point") if over else None,
                "over_odds": over.get("price") if over else None,
                "under_odds": under.get("price") if under else None,
                "bookmaker": bookmaker["title"],
                "ingested_at": ingested.isoformat(),
            }
        )

    return rows