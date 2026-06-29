# Databricks notebook source
# MAGIC %md
# MAGIC # Ingest nflverse play-by-play
# MAGIC Loads prior-season REG + POST play-by-play into `nflverse_pbp`.

# COMMAND ----------

dbutils.widgets.text("catalog", "main", "Unity Catalog")
dbutils.widgets.text("schema", "nfl", "Schema")
dbutils.widgets.text("pbp_season", "2025", "Play-by-play season")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
pbp_season = int(dbutils.widgets.get("pbp_season"))

pbp_table = f"{catalog}.{schema}.nflverse_pbp"

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

from nfl_odds.nflverse_data import fetch_play_by_play
from nfl_odds.spark_io import pandas_to_spark

ingested_at = datetime.now(timezone.utc)

pbp_df = fetch_play_by_play(pbp_season, season_types=("REG", "POST"))

print(
    f"PBP {pbp_season}: {len(pbp_df):,} plays, "
    f"{pbp_df['game_id'].nunique()} games, "
    f"types={pbp_df['season_type'].value_counts().to_dict()}"
)

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

pdf = pbp_df.copy()
pdf["ingested_at"] = ingested_at

(
    pandas_to_spark(spark, pdf)
    .write.format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(pbp_table)
)

# COMMAND ----------

display(spark.table(pbp_table).groupBy("season_type").count())