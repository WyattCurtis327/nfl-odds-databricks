"""Email Monte Carlo picks from Delta using a local SendGrid API key."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_odds.notifications import format_predictions_email_html, send_email_sendgrid

DEFAULT_WAREHOUSE_ID = "abae422499df211c"
DEFAULT_PROFILE = "wyatts_databricks"


def _load_sendgrid_key() -> str:
    return (
        os.environ.get("SENDGRID_API_KEY")
        or os.environ.get("sendgrid_api_key")
        or ""
    ).strip()


def _load_from_email(fallback: str) -> str:
    return (
        os.environ.get("SENDGRID_FROM_EMAIL")
        or os.environ.get("SENDGRID_FROM")
        or fallback
    ).strip()


def fetch_predictions_sql(
    *,
    catalog: str,
    schema: str,
    season: int,
    week: int,
    profile: str,
    warehouse_id: str,
) -> pd.DataFrame:
    sql = f"""
    SELECT *
    FROM {catalog}.{schema}.monte_carlo_predictions
    WHERE season = {season} AND week = {week}
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY game_id
      ORDER BY predicted_at DESC
    ) = 1
    ORDER BY gameday, kickoff_et
    """
    payload = {
        "warehouse_id": warehouse_id,
        "statement": sql,
        "wait_timeout": "50s",
    }
    staging = ROOT / "staging" / "email_query.json"
    staging.parent.mkdir(exist_ok=True)
    staging.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        [
            "databricks",
            "api",
            "post",
            "/api/2.0/sql/statements",
            "--profile",
            profile,
            "-o",
            "json",
            "--json",
            f"@{staging}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    response = json.loads(result.stdout)
    if response.get("status", {}).get("state") != "SUCCEEDED":
        raise RuntimeError(f"SQL query failed: {response}")

    manifest = response["manifest"]["schema"]["columns"]
    columns = [col["name"] for col in manifest]
    rows = response.get("result", {}).get("data_array", [])
    return pd.DataFrame(rows, columns=columns)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default="workspace")
    parser.add_argument("--schema", default="nfl")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--to", dest="to_email", default="wyatt_curtis@hotmail.com")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--warehouse-id", default=DEFAULT_WAREHOUSE_ID)
    args = parser.parse_args()

    api_key = _load_sendgrid_key()
    if not api_key:
        raise SystemExit(
            "Set SENDGRID_API_KEY in your environment before running this script."
        )

    from_email = _load_from_email(args.to_email)
    picks = fetch_predictions_sql(
        catalog=args.catalog,
        schema=args.schema,
        season=args.season,
        week=args.week,
        profile=args.profile,
        warehouse_id=args.warehouse_id,
    )
    if picks.empty:
        raise SystemExit(
            f"No predictions found for season={args.season}, week={args.week}."
        )

    prediction_run_id = str(picks.iloc[0]["prediction_run_id"])
    html = format_predictions_email_html(
        picks,
        season=args.season,
        week=args.week,
        prediction_run_id=prediction_run_id,
    )
    send_email_sendgrid(
        api_key=api_key,
        to_email=args.to_email,
        subject=f"NFL Monte Carlo picks — {args.season} Week {args.week}",
        html_content=html,
        from_email=from_email,
    )
    print(f"Emailed {len(picks)} games to {args.to_email}")


if __name__ == "__main__":
    main()