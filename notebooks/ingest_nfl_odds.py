# Databricks notebook source
# MAGIC %md
# MAGIC # Ingest NFL odds
# MAGIC Fetches odds from The Odds API, joins nflverse `game_id`, and writes Delta tables.

# COMMAND ----------

dbutils.widgets.text("catalog", "main", "Unity Catalog")
dbutils.widgets.text("schema", "nfl", "Schema")
dbutils.widgets.text("season", "2026", "NFL season")
dbutils.widgets.text("secret_scope", "nfl", "Secret scope")
dbutils.widgets.text("secret_key", "odds_api_key", "Secret key")
dbutils.widgets.text(
    "odds_staging_path",
    "../staging/odds_latest.json",
    "Local staged odds JSON (used when serverless cannot reach Odds API)",
)

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
season = int(dbutils.widgets.get("season"))
secret_scope = dbutils.widgets.get("secret_scope")
secret_key = dbutils.widgets.get("secret_key")
odds_staging_path = dbutils.widgets.get("odds_staging_path").strip()

bronze_raw = f"{catalog}.{schema}.odds_api_nfl_raw"
bronze_schedule = f"{catalog}.{schema}.nflverse_schedule"
silver_lines = f"{catalog}.{schema}.nfl_odds_lines"
gold_game_odds = f"{catalog}.{schema}.nfl_game_odds"

# COMMAND ----------

import json
import os
import sys
from datetime import datetime, timezone


def _add_src_to_path() -> str:
    candidates = [
        os.path.abspath(os.path.join(os.getcwd(), "..", "src")),
        os.path.abspath(os.path.join(os.getcwd(), "src")),
    ]
    for path in candidates:
        if os.path.isdir(path):
            sys.path.insert(0, path)
            return path
    return ""


_add_src_to_path()

import pandas as pd

from nfl_odds.fetch import OddsApiError, fetch_nfl_odds
from nfl_odds.schedule import fetch_nflverse_schedule
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
schedule_df = fetch_nflverse_schedule(season)
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

schedule_spark = pandas_to_spark(spark, schedule_df)
schedule_spark.write.format("delta").mode("overwrite").option(
    "overwriteSchema", "true"
).saveAsTable(bronze_schedule)

# COMMAND ----------

line_rows = flatten_odds(odds_games, schedule_df=schedule_df, ingested_at=ingested_at)
game_rows = to_game_odds_rows(odds_games, schedule_df, ingested_at=ingested_at)

pandas_to_spark(spark, pd.DataFrame(line_rows)).write.format("delta").mode("append").saveAsTable(
    silver_lines
)
pandas_to_spark(spark, pd.DataFrame(game_rows)).write.format("delta").mode("append").saveAsTable(
    gold_game_odds
)

# COMMAND ----------

display(spark.table(gold_game_odds).orderBy("week", "kickoff_et").limit(20))