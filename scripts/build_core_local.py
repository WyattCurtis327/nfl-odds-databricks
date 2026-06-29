"""Build local core dimension outputs with ID-safe keys."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_odds.core import (
    build_game_dimension,
    build_player_dimension,
    extract_pbp_player_roles,
)

OUT_DIR = ROOT / "output"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    ingested_at = datetime.now(timezone.utc).isoformat()

    rosters = pd.read_csv(OUT_DIR / "rosters_2026.csv")
    schedule = pd.read_csv(OUT_DIR / "schedule_2026_reg.csv")
    pbp = pd.read_parquet(OUT_DIR / "play_by_play_2025.parquet")

    players = build_player_dimension(rosters)
    games = build_game_dimension(schedule)
    roles = extract_pbp_player_roles(pbp)

    players.to_csv(OUT_DIR / "dim_players.csv", index=False)
    games.to_csv(OUT_DIR / "dim_games.csv", index=False)
    roles.to_parquet(OUT_DIR / "pbp_player_roles.parquet", index=False)

    collisions = int(players["name_collision"].sum())
    print(f"dim_players: {len(players)} rows ({collisions} collision labels)")
    print(f"dim_games: {len(games)} rows")
    print(f"pbp_player_roles: {len(roles)} rows")
    print(f"ingested_at: {ingested_at}")
    print(f"Wrote files to {OUT_DIR}")


if __name__ == "__main__":
    main()