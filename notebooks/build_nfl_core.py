# Databricks notebook source
# MAGIC %md
# MAGIC # Build NFL core dimensions
# MAGIC Creates `dim_players` (gsis_id key), `dim_games` (game_id key), and ID-safe bridge tables.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace", "Unity Catalog")
dbutils.widgets.text("schema", "nfl", "Schema")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

dim_players = f"{catalog}.{schema}.dim_players"
dim_games = f"{catalog}.{schema}.dim_games"
pbp_player_roles = f"{catalog}.{schema}.pbp_player_roles"
game_odds_latest = f"{catalog}.{schema}.game_odds_latest"
pbp_table = f"{catalog}.{schema}.nflverse_pbp"

# COMMAND ----------

from datetime import datetime, timezone

import pandas as pd

from nfl_odds.core import (
    build_game_dimension,
    build_player_dimension,
    extract_pbp_player_roles,
)
from nfl_odds.spark_io import pandas_to_spark

ingested_at = datetime.now(timezone.utc)

rosters_pdf = spark.table(f"{catalog}.{schema}.nflverse_rosters").toPandas()
schedule_pdf = spark.table(f"{catalog}.{schema}.nflverse_schedule").toPandas()

if spark.catalog.tableExists(pbp_table):
    pbp_pdf = spark.table(pbp_table).toPandas()
    print(f"Loaded {len(pbp_pdf)} PBP rows from {pbp_table}")
else:
    pbp_pdf = pd.DataFrame()
    print(f"PBP table {pbp_table} not found; writing empty pbp_player_roles")

players_df = build_player_dimension(rosters_pdf)
games_df = build_game_dimension(schedule_pdf)
roles_df = extract_pbp_player_roles(pbp_pdf)

players_df["ingested_at"] = ingested_at
games_df["ingested_at"] = ingested_at
roles_df["ingested_at"] = ingested_at

print(f"dim_players: {len(players_df)} rows")
print(f"name collisions disambiguated: {int(players_df['name_collision'].sum())}")
print(f"dim_games: {len(games_df)} rows")
print(f"pbp_player_roles: {len(roles_df)} rows")

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

for pdf, table in [
    (players_df, dim_players),
    (games_df, dim_games),
    (roles_df, pbp_player_roles),
]:
    (
        pandas_to_spark(spark, pdf)
        .write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(table)
    )

# COMMAND ----------

# Latest odds per official game_id (not odds_api_id or team names)
spark.sql(
    f"""
    CREATE OR REPLACE TABLE {game_odds_latest} AS
    SELECT *
    FROM (
      SELECT
        o.*,
        ROW_NUMBER() OVER (
          PARTITION BY game_id, bookmaker
          ORDER BY ingested_at DESC
        ) AS rn
      FROM {catalog}.{schema}.nfl_game_odds o
      WHERE game_id IS NOT NULL
    )
    WHERE rn = 1
    """
)

display(spark.table(game_odds_latest).orderBy("week", "kickoff_et").limit(20))