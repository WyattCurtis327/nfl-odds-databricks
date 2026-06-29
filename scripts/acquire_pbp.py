"""Download prior-season nflverse play-by-play locally."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_odds.nflverse_data import fetch_play_by_play

PBP_SEASON = 2025
OUT_DIR = ROOT / "output"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    ingested_at = datetime.now(timezone.utc).isoformat()

    pbp = fetch_play_by_play(PBP_SEASON, season_types=("REG", "POST"))
    pbp_path = OUT_DIR / f"play_by_play_{PBP_SEASON}.parquet"
    pbp.to_parquet(pbp_path, index=False)

    print(f"PBP {PBP_SEASON}: {len(pbp):,} plays across {pbp['game_id'].nunique()} games")
    print(f"  season types: {pbp['season_type'].value_counts().to_dict()}")
    print(f"  ingested_at: {ingested_at}")
    print(f"Wrote {pbp_path}")


if __name__ == "__main__":
    main()