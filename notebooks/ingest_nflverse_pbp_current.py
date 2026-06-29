# Databricks notebook source
# MAGIC %md
# MAGIC # Ingest elapsed-week 2026 play-by-play
# MAGIC Loads nflverse PBP for completed regular-season weeks in the current year.

# COMMAND ----------

dbutils.widgets.text("catalog", "main", "Unity Catalog")
dbutils.widgets.text("schema", "nfl", "Schema")
dbutils.widgets.text("pbp_season", "2026", "Current PBP season")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
pbp_season = int(dbutils.widgets.get("pbp_season"))

pbp_table = f"{catalog}.{schema}.nflverse_pbp_current"
weeks_table = f"{catalog}.{schema}.nflverse_pbp_elapsed_weeks"

# COMMAND ----------

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

from nfl_odds.nflverse_data import (
    PbpNotAvailableError,
    fetch_play_by_play_for_elapsed_weeks,
    fetch_season_schedule,
    get_elapsed_weeks,
)
from nfl_odds.spark_io import pandas_to_spark

ingested_at = datetime.now(timezone.utc)
schedule_df = fetch_season_schedule(pbp_season, game_types=("REG",))
elapsed_weeks = get_elapsed_weeks(schedule_df, pbp_season)

print(f"Elapsed REG weeks for {pbp_season}: {elapsed_weeks or 'none'}")

if not elapsed_weeks:
    dbutils.notebook.exit("No elapsed weeks yet; skipping PBP ingest.")

try:
    pbp_df, loaded_weeks = fetch_play_by_play_for_elapsed_weeks(pbp_season)
except PbpNotAvailableError as exc:
    dbutils.notebook.exit(f"PBP not published yet for {pbp_season}: {exc}")

print(
    f"Loaded {len(pbp_df):,} plays for weeks {loaded_weeks}; "
    f"{pbp_df['game_id'].nunique() if not pbp_df.empty else 0} games"
)

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

if pbp_df.empty:
    dbutils.notebook.exit("Elapsed weeks identified, but no matching PBP rows returned.")

pbp_pdf = pbp_df.copy()
pbp_pdf["ingested_at"] = ingested_at

(
    pandas_to_spark(spark, pbp_pdf)
    .write.format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(pbp_table)
)

weeks_pdf = pd.DataFrame(
    {
        "season": [pbp_season],
        "elapsed_weeks": [",".join(str(w) for w in loaded_weeks)],
        "week_count": [len(loaded_weeks)],
        "play_count": [len(pbp_df)],
        "game_count": [int(pbp_df["game_id"].nunique())],
        "ingested_at": [ingested_at],
    }
)

(
    pandas_to_spark(spark, weeks_pdf)
    .write.format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(weeks_table)
)

# COMMAND ----------

display(spark.table(pbp_table).groupBy("week").count().orderBy("week"))