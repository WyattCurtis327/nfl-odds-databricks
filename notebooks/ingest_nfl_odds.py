# Databricks notebook source
# MAGIC %md
# MAGIC # Ingest NFL odds
# MAGIC Fetches odds from The Odds API, joins nflverse `game_id`, and writes Delta tables.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace", "Unity Catalog")
dbutils.widgets.text("schema", "nfl", "Schema")
dbutils.widgets.text("season", "2026", "NFL season")
dbutils.widgets.text("secret_scope", "nfl", "Secret scope")
dbutils.widgets.text("secret_key", "odds_api_key", "Secret key")
dbutils.widgets.text(
    "odds_staging_path",
    "../staging/odds_latest.json",
    "Local staged odds JSON (used when serverless cannot reach Odds API)",
)
dbutils.widgets.text("min_match_rate", "0.9", "Minimum game_id match rate (0-1)")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
season = int(dbutils.widgets.get("season"))
secret_scope = dbutils.widgets.get("secret_scope")
secret_key = dbutils.widgets.get("secret_key")
odds_staging_path = dbutils.widgets.get("odds_staging_path").strip()
min_match_rate = float(dbutils.widgets.get("min_match_rate"))

bronze_raw = f"{catalog}.{schema}.odds_api_nfl_raw"
bronze_schedule = f"{catalog}.{schema}.nflverse_schedule"
silver_lines = f"{catalog}.{schema}.nfl_odds_lines"
gold_game_odds = f"{catalog}.{schema}.nfl_game_odds"
quality_table = f"{catalog}.{schema}.odds_match_quality"

# COMMAND ----------

import json
import os
from datetime import datetime, timezone

import pandas as pd

from nfl_odds.fetch import OddsApiError, fetch_nfl_odds
from nfl_odds.quality import assess_game_id_match_rate
from nfl_odds.spark_io import pandas_to_spark
from nfl_odds.transform import flatten_odds, to_game_odds_rows


def _resolve_staging_path(path: str) -> str:
    if not path:
        return ""
    if os.path.isabs(path) and os.path.isfile(path):
        return path
    candidates = [
        os.path.abspath(os.path.join(os.getcwd(), path)),
        os.path.abspath(os.path.join(os.getcwd(), "..", path)),
        os.path.abspath(os.path.join(os.getcwd(), "..", "files", path.lstrip("./"))),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return ""


def _load_staged_odds(path: str) -> tuple[list, dict]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["games"], payload.get("headers", {})


ingested_at = datetime.now(timezone.utc)

if not spark.catalog.tableExists(bronze_schedule):
    raise RuntimeError(
        f"Missing {bronze_schedule}. Run ingest_nflverse before ingest_odds."
    )

schedule_df = spark.table(bronze_schedule).toPandas()
staging_file = _resolve_staging_path(odds_staging_path)

if staging_file:
    odds_games, headers = _load_staged_odds(staging_file)
    source = f"staged file: {staging_file}"
else:
    api_key = dbutils.secrets.get(scope=secret_scope, key=secret_key).strip()
    try:
        odds_games, headers = fetch_nfl_odds(api_key)
        source = "odds api"
    except (OddsApiError, ConnectionError) as exc:
        raise RuntimeError(
            "Odds API unavailable from serverless and no staged odds file found. "
            "Run scripts/stage_odds.py locally, deploy, then rerun."
        ) from exc

print(
    "Loaded",
    len(odds_games),
    "games from",
    source + ";",
    "requests remaining:",
    headers.get("x-requests-remaining"),
)

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

raw_df = spark.createDataFrame(
    [
        {
            "ingested_at": ingested_at,
            "season": season,
            "payload": json.dumps(odds_games),
            "requests_remaining": headers.get("x-requests-remaining"),
            "requests_used": headers.get("x-requests-used"),
        }
    ]
)
raw_df.write.format("delta").mode("append").saveAsTable(bronze_raw)

# COMMAND ----------

line_rows = flatten_odds(odds_games, schedule_df=schedule_df, ingested_at=ingested_at)
game_rows = to_game_odds_rows(odds_games, schedule_df, ingested_at=ingested_at)

match_stats = assess_game_id_match_rate(game_rows, min_rate=min_match_rate)
quality_row = {
    **match_stats,
    "ingested_at": ingested_at.isoformat(),
    "season": season,
    "source": source,
}
pandas_to_spark(spark, pd.DataFrame([quality_row])).write.format("delta").mode(
    "append"
).option("mergeSchema", "true").saveAsTable(quality_table)

print(
    "game_id match rate:",
    f"{match_stats['matched_games']}/{match_stats['total_games']}",
    f"({match_stats['match_rate']:.1%})",
)

if not match_stats["passed"]:
    unmatched = [row for row in game_rows if not row.get("game_id")]
    preview = [
        {
            "away_team": row.get("away_team"),
            "home_team": row.get("home_team"),
            "gameday": row.get("gameday"),
        }
        for row in unmatched[:5]
    ]
    raise RuntimeError(
        f"game_id match rate {match_stats['match_rate']:.1%} below minimum "
        f"{min_match_rate:.1%}. Sample unmatched games: {preview}"
    )

pandas_to_spark(spark, pd.DataFrame(line_rows)).write.format("delta").mode("append").saveAsTable(
    silver_lines
)
pandas_to_spark(spark, pd.DataFrame(game_rows)).write.format("delta").mode("append").saveAsTable(
    gold_game_odds
)

# COMMAND ----------

display(spark.table(gold_game_odds).orderBy("week", "kickoff_et").limit(20))