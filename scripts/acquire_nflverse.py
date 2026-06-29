"""Download nflverse rosters and schedule to local output."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_odds.nflverse_data import fetch_rosters, fetch_season_schedule

ROSTER_SEASON = 2026
SCHEDULE_SEASON = 2026
OUT_DIR = ROOT / "output"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    ingested_at = datetime.now(timezone.utc).isoformat()

    rosters = fetch_rosters(ROSTER_SEASON)
    schedule = fetch_season_schedule(SCHEDULE_SEASON, game_types=("REG",))

    rosters.to_csv(OUT_DIR / f"rosters_{ROSTER_SEASON}.csv", index=False)
    schedule.to_csv(OUT_DIR / f"schedule_{SCHEDULE_SEASON}_reg.csv", index=False)

    print(f"Rosters {ROSTER_SEASON}: {len(rosters):,} rows, {rosters['team'].nunique()} teams")
    print(f"Schedule {SCHEDULE_SEASON} REG: {len(schedule)} games")
    print(f"ingested_at: {ingested_at}")
    print(f"Wrote files to {OUT_DIR}")


if __name__ == "__main__":
    main()