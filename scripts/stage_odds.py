"""Fetch odds locally and stage them for Databricks serverless ingest."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "staging" / "odds_latest.json"
OUTPUT = ROOT / "output" / "nfl_odds_raw.json"


def main() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "run_local.py")], check=True)
    STAGING.parent.mkdir(exist_ok=True)
    shutil.copy2(OUTPUT, STAGING)
    print(f"Staged odds for Databricks ingest: {STAGING}")


if __name__ == "__main__":
    main()