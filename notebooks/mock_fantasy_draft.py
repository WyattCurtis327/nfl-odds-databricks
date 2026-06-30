# Databricks notebook source
# MAGIC %md
# MAGIC # Mock fantasy draft
# MAGIC Simulates a 12-team snake draft using prior-season nflverse play-by-play analytics.
# MAGIC
# MAGIC **Roster:** 3 WR · 2 RB · 1 FLEX (RB/WR/TE) · 1 TE · 1 QB · 1 K · 1 DEF
# MAGIC
# MAGIC Set **Draft position** to your slot (1–12). The notebook ranks players by PPR points per game
# MAGIC from `workspace.nfl` Delta tables and drafts the best available fit for every team.
# MAGIC
# MAGIC **Source tables:** `workspace.nfl.nflverse_pbp`, `workspace.nfl.nflverse_pbp_current`,
# MAGIC `workspace.nfl.nflverse_rosters`, `workspace.nfl.nflverse_schedule`

# COMMAND ----------

dbutils.widgets.dropdown(
    "draft_position",
    "1",
    [str(i) for i in range(1, 13)],
    "Draft position (1-12)",
)
dbutils.widgets.text("catalog", "workspace", "Unity Catalog")
dbutils.widgets.text("schema", "nfl", "Schema")
dbutils.widgets.text("pbp_season", "2025", "Prior-season PBP analytics")
dbutils.widgets.text("current_pbp_season", "2026", "In-season PBP analytics")
dbutils.widgets.text("roster_season", "2026", "Roster season for positions")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
pbp_season = int(dbutils.widgets.get("pbp_season"))
current_pbp_season = int(dbutils.widgets.get("current_pbp_season"))
roster_season = dbutils.widgets.get("roster_season")
draft_position = int(dbutils.widgets.get("draft_position"))

pbp_table = f"{catalog}.{schema}.nflverse_pbp"
current_pbp_table = f"{catalog}.{schema}.nflverse_pbp_current"
rosters_table = f"{catalog}.{schema}.nflverse_rosters"
schedule_table = f"{catalog}.{schema}.nflverse_schedule"

print(f"Reading prior PBP from:   {pbp_table} (season {pbp_season})")
print(f"Reading current PBP from: {current_pbp_table} (season {current_pbp_season})")
print(f"Reading rosters from:   {rosters_table}")
print(f"Reading schedule from:  {schedule_table}")

# COMMAND ----------

import pandas as pd

from nfl_odds.fantasy import (
    ROSTER_SLOTS,
    build_fantasy_rankings,
    draft_log_frame,
    run_mock_draft,
    snake_pick_order,
)
from nfl_odds.simulation import combine_pbp_seasons

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load PBP analytics

# COMMAND ----------

prior_pbp_pdf = spark.table(pbp_table).toPandas()
if spark.catalog.tableExists(current_pbp_table):
    current_pbp_pdf = spark.table(current_pbp_table).toPandas()
else:
    current_pbp_pdf = pd.DataFrame()
    print(f"Current PBP table {current_pbp_table} not found; using prior season only")

pbp_pdf = combine_pbp_seasons(
    prior_pbp_pdf,
    current_pbp_pdf,
    prior_season=pbp_season,
    current_season=current_pbp_season,
)
rosters_pdf = spark.table(rosters_table).toPandas()
schedule_pdf = spark.table(schedule_table).toPandas()

if "season" in rosters_pdf.columns:
    rosters_pdf = rosters_pdf[rosters_pdf["season"] == int(roster_season)].copy()

rankings = build_fantasy_rankings(pbp_pdf, rosters_pdf, schedule=schedule_pdf)

print(
    f"PBP season {pbp_season}: {len(pbp_pdf):,} plays → "
    f"{len(rankings):,} draftable players"
)
display(
    rankings.groupby("position")
    .agg(players=("player_id", "count"), top_ppg=("points_per_game", "max"))
    .reset_index()
    .sort_values("position")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Top available by position

# COMMAND ----------

for position in ["QB", "RB", "WR", "TE", "K", "DEF"]:
    pos_rank = rankings[rankings["position"] == position].head(12)
    if pos_rank.empty:
        continue
    print(f"\n--- {position} ---")
    display(
        pos_rank[
            ["rank", "player_name", "team", "games", "total_points", "points_per_game"]
        ]
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run snake draft
# MAGIC Pick order for your slot: rounds alternate direction each round (1→12, then 12→1, …).

# COMMAND ----------

picks, rosters = run_mock_draft(rankings, draft_position)
draft_log = draft_log_frame(picks)

user_picks = draft_log[draft_log["user_pick"]]
print(f"Your draft position: {draft_position}")
print(f"Total picks: {len(draft_log)} ({sum(ROSTER_SLOTS.values())} per team)")
print("\nYour picks:")
display(user_picks)

# COMMAND ----------

user_roster = rosters[draft_position].to_frame()
print("Your starting lineup")
display(user_roster)

# COMMAND ----------

print("Full draft board")
display(spark.createDataFrame(draft_log))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Draft order reference
# MAGIC First 24 picks for a 12-team snake (your slot highlighted).

# COMMAND ----------

order_rows = []
for pick_no, team_slot in enumerate(snake_pick_order(), start=1):
    order_rows.append(
        {
            "pick": pick_no,
            "round": (pick_no - 1) // 12 + 1,
            "team": team_slot,
            "your_pick": team_slot == draft_position,
        }
    )

display(spark.createDataFrame(pd.DataFrame(order_rows)).limit(24))