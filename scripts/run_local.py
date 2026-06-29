"""Run the NFL odds pipeline locally and write CSV outputs."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_odds.fetch import fetch_nfl_odds
from nfl_odds.schedule import fetch_nflverse_schedule
from nfl_odds.transform import flatten_odds, to_game_odds_rows

SEASON = 2026
OUT_DIR = ROOT / "output"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    ingested_at = datetime.now(timezone.utc)

    odds_games, headers = fetch_nfl_odds()
    schedule_df = fetch_nflverse_schedule(SEASON)

    line_rows = flatten_odds(odds_games, schedule_df=schedule_df, ingested_at=ingested_at)
    game_rows = to_game_odds_rows(odds_games, schedule_df, ingested_at=ingested_at)

    pd.DataFrame(line_rows).to_csv(OUT_DIR / "nfl_odds_lines.csv", index=False)
    pd.DataFrame(game_rows).to_csv(OUT_DIR / "nfl_game_odds.csv", index=False)

    with (OUT_DIR / "nfl_odds_raw.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "ingested_at": ingested_at.isoformat(),
                "headers": headers,
                "games": odds_games,
            },
            f,
            indent=2,
        )

    matched = sum(1 for row in game_rows if row["game_id"])
    print(f"Fetched {len(odds_games)} games")
    print(f"Matched {matched}/{len(game_rows)} to official game_id")
    print(f"Requests remaining: {headers.get('x-requests-remaining')}")
    print(f"Wrote files to {OUT_DIR}")


if __name__ == "__main__":
    main()