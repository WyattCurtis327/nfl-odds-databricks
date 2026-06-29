# Databricks notebook source
# MAGIC %md
# MAGIC # Ingest nflverse rosters and schedule
# MAGIC Loads current rosters and regular-season schedule (no play-by-play).

# COMMAND ----------

dbutils.widgets.text("catalog", "main", "Unity Catalog")
dbutils.widgets.text("schema", "nfl", "Schema")
dbutils.widgets.text("roster_season", "2026", "Roster season")
dbutils.widgets.text("schedule_season", "2026", "Schedule season")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
roster_season = int(dbutils.widgets.get("roster_season"))
schedule_season = int(dbutils.widgets.get("schedule_season"))

rosters_table = f"{catalog}.{schema}.nflverse_rosters"
schedule_table = f"{catalog}.{schema}.nflverse_schedule"

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

from nfl_odds.nflverse_data import fetch_rosters, fetch_season_schedule
from nfl_odds.spark_io import pandas_to_spark

ingested_at = datetime.now(timezone.utc)

rosters_df = fetch_rosters(roster_season)
schedule_df = fetch_season_schedule(schedule_season, game_types=("REG",))

print(f"Rosters {roster_season}: {len(rosters_df):,} rows")
print(f"Schedule {schedule_season}: {len(schedule_df)} regular-season games")

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

for frame, table in [(rosters_df, rosters_table), (schedule_df, schedule_table)]:
    pdf = frame.copy()
    pdf["ingested_at"] = ingested_at
    (
        pandas_to_spark(spark, pdf)
        .write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(table)
    )

# COMMAND ----------

display(spark.table(schedule_table).orderBy("week", "gameday").limit(20))