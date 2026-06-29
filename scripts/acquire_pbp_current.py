"""Download elapsed-week current-season PBP locally."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_odds.nflverse_data import (
    PbpNotAvailableError,
    fetch_play_by_play_for_elapsed_weeks,
    fetch_season_schedule,
    get_elapsed_weeks,
)

CURRENT_SEASON = 2026
OUT_DIR = ROOT / "output"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    ingested_at = datetime.now(timezone.utc).isoformat()

    schedule = fetch_season_schedule(CURRENT_SEASON, game_types=("REG",))
    elapsed_weeks = get_elapsed_weeks(schedule, CURRENT_SEASON)
    print(f"Elapsed weeks: {elapsed_weeks or 'none'}")

    if not elapsed_weeks:
        print("No elapsed weeks yet.")
        return

    try:
        pbp, loaded_weeks = fetch_play_by_play_for_elapsed_weeks(CURRENT_SEASON)
    except PbpNotAvailableError as exc:
        print(exc)
        return

    out_path = OUT_DIR / f"play_by_play_{CURRENT_SEASON}_elapsed.parquet"
    pbp.to_parquet(out_path, index=False)
    print(f"Loaded {len(pbp):,} plays for weeks {loaded_weeks}")
    print(f"ingested_at: {ingested_at}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()