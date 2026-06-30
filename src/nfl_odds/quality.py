"""Data quality checks for ingest pipelines."""

from __future__ import annotations

from typing import Any


def assess_game_id_match_rate(
    game_rows: list[dict[str, Any]],
    *,
    min_rate: float = 0.9,
) -> dict[str, Any]:
    """Return match stats for odds-to-schedule game_id joins."""
    total = len(game_rows)
    matched = sum(1 for row in game_rows if row.get("game_id"))
    rate = (matched / total) if total else 1.0
    return {
        "total_games": total,
        "matched_games": matched,
        "unmatched_games": total - matched,
        "match_rate": round(rate, 4),
        "min_rate": min_rate,
        "passed": rate >= min_rate,
    }