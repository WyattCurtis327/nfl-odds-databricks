# Databricks notebook source
# MAGIC %md
# MAGIC # Monte Carlo weekly picks
# MAGIC Simulates upcoming NFL games using prior-season play-by-play scoring rates and current
# MAGIC betting lines to estimate spread and total cover probabilities.
# MAGIC
# MAGIC **Outputs per game:**
# MAGIC - ATS pick (away/home) and cover probability
# MAGIC - Total pick (OVER/UNDER) and cover probability
# MAGIC - Projected scores from PBP + market blend
# MAGIC
# MAGIC **Source tables:** `workspace.nfl.nflverse_pbp`, `workspace.nfl.game_odds_latest`,
# MAGIC `workspace.nfl.nflverse_schedule`
# MAGIC
# MAGIC **Logs to:** `workspace.nfl.monte_carlo_predictions` and MLflow experiment
# MAGIC `/Shared/nfl_monte_carlo`. Grade results after the week with `monte_carlo_weekly_accuracy`.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace", "Unity Catalog")
dbutils.widgets.text("schema", "nfl", "Schema")
dbutils.widgets.text("season", "2026", "Schedule / odds season")
dbutils.widgets.text("pbp_season", "2025", "PBP analytics season")
dbutils.widgets.text("target_week", "1", "Week to simulate (blank = next unplayed)")
dbutils.widgets.text("n_simulations", "10000", "Monte Carlo simulations per game")
dbutils.widgets.text("market_blend", "0.35", "Weight given to market lines (0-1)")
dbutils.widgets.text("pick_threshold", "0.55", "Min confidence to highlight a pick")
dbutils.widgets.text(
    "mlflow_experiment",
    "/Shared/nfl_monte_carlo",
    "MLflow experiment path",
)
dbutils.widgets.dropdown(
    "log_predictions",
    "true",
    ["true", "false"],
    "Append predictions to Delta + MLflow",
)
dbutils.widgets.dropdown(
    "send_email",
    "true",
    ["true", "false"],
    "Email picks after run (requires SendGrid secret)",
)
dbutils.widgets.text(
    "notify_email",
    "wyatt_curtis@hotmail.com",
    "Recipient email address",
)

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
season = int(dbutils.widgets.get("season"))
pbp_season = int(dbutils.widgets.get("pbp_season"))
target_week_raw = dbutils.widgets.get("target_week").strip()
n_simulations = int(dbutils.widgets.get("n_simulations"))
market_blend = float(dbutils.widgets.get("market_blend"))
pick_threshold = float(dbutils.widgets.get("pick_threshold"))
mlflow_experiment = dbutils.widgets.get("mlflow_experiment").strip()
log_predictions = dbutils.widgets.get("log_predictions").lower() == "true"
send_email = dbutils.widgets.get("send_email").lower() == "true"
notify_email = dbutils.widgets.get("notify_email").strip()

pbp_table = f"{catalog}.{schema}.nflverse_pbp"
odds_table = f"{catalog}.{schema}.game_odds_latest"
schedule_table = f"{catalog}.{schema}.nflverse_schedule"
predictions_table = f"{catalog}.{schema}.monte_carlo_predictions"

print(f"PBP analytics:  {pbp_table} (season {pbp_season})")
print(f"Odds lines:     {odds_table}")
print(f"Schedule:       {schedule_table} (season {season})")

# COMMAND ----------

import os
import sys


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

from nfl_odds.simulation import (
    SimulationConfig,
    compute_team_scoring_profiles,
    infer_next_week,
    new_prediction_run_id,
    prepare_prediction_log,
    simulate_weekly_picks,
)
from nfl_odds.notifications import format_predictions_email_html, send_email_sendgrid
from nfl_odds.spark_io import pandas_to_spark

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load data

# COMMAND ----------

pbp_pdf = spark.table(pbp_table).toPandas()
odds_pdf = spark.table(odds_table).toPandas()
schedule_pdf = spark.table(schedule_table).toPandas()

if "season" in pbp_pdf.columns:
    pbp_pdf = pbp_pdf[pbp_pdf["season"] == pbp_season].copy()
if "season" in schedule_pdf.columns:
    schedule_pdf = schedule_pdf[schedule_pdf["season"] == season].copy()

if target_week_raw:
    target_week = int(target_week_raw)
else:
    target_week = infer_next_week(schedule_pdf, season=season)

if target_week is None:
    raise ValueError("No unplayed weeks found in schedule; set target_week explicitly.")

profiles = compute_team_scoring_profiles(pbp_pdf)
config = SimulationConfig(
    n_simulations=n_simulations,
    market_blend=market_blend,
    pick_threshold=pick_threshold,
)

print(f"Simulating week {target_week} with {n_simulations:,} runs per game")
print(f"Team scoring profiles: {len(profiles)} teams")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Team scoring profiles (PBP)

# COMMAND ----------

display(
    profiles.sort_values("points_for_mean", ascending=False)[
        [
            "team",
            "games",
            "points_for_mean",
            "points_for_std",
            "points_against_mean",
        ]
    ]
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Monte Carlo picks

# COMMAND ----------

picks = simulate_weekly_picks(
    odds_pdf,
    profiles,
    week=target_week,
    schedule=schedule_pdf,
    config=config,
)

if picks.empty:
    raise ValueError(
        f"No odds rows found for week {target_week}. "
        "Run the weekly odds pipeline or stage odds for this week."
    )

display_cols = [
    "game_id",
    "gameday",
    "kickoff_et",
    "away_abbr",
    "home_abbr",
    "away_spread",
    "total_line",
    "proj_away_score",
    "proj_home_score",
    "proj_total",
    "spread_pick",
    "spread_confidence",
    "away_cover_pct",
    "home_cover_pct",
    "total_pick",
    "total_confidence",
    "over_pct",
    "under_pct",
    "bookmaker",
]

summary = picks[display_cols].copy()
summary["spread_confidence"] = (summary["spread_confidence"] * 100).round(1)
summary["total_confidence"] = (summary["total_confidence"] * 100).round(1)
summary["away_cover_pct"] = (summary["away_cover_pct"] * 100).round(1)
summary["home_cover_pct"] = (summary["home_cover_pct"] * 100).round(1)
summary["over_pct"] = (summary["over_pct"] * 100).round(1)
summary["under_pct"] = (summary["under_pct"] * 100).round(1)

print(f"Week {target_week}: {len(summary)} games simulated")
display(spark.createDataFrame(summary))

# COMMAND ----------

# MAGIC %md
# MAGIC ## High-confidence picks
# MAGIC Picks where simulated cover probability meets the threshold (default 55%).

# COMMAND ----------

spread_conf = picks[
    picks["spread_confidence"].notna()
    & (picks["spread_confidence"] >= pick_threshold)
].copy()
total_conf = picks[
    picks["total_confidence"].notna() & (picks["total_confidence"] >= pick_threshold)
].copy()

print("Spread picks at/above threshold")
if spread_conf.empty:
    print("  (none)")
else:
    display(
        spark.createDataFrame(
            spread_conf[
                [
                    "away_abbr",
                    "home_abbr",
                    "away_spread",
                    "spread_pick",
                    "spread_confidence",
                    "proj_away_score",
                    "proj_home_score",
                ]
            ]
        )
    )

print("Total picks at/above threshold")
if total_conf.empty:
    print("  (none)")
else:
    display(
        spark.createDataFrame(
            total_conf[
                [
                    "away_abbr",
                    "home_abbr",
                    "total_line",
                    "total_pick",
                    "total_confidence",
                    "proj_total",
                ]
            ]
        )
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Full simulation detail

# COMMAND ----------

display(spark.createDataFrame(picks))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Log predictions (Delta + MLflow)
# MAGIC Stores an immutable run so accuracy can be graded after the week completes.

# COMMAND ----------

prediction_run_id = new_prediction_run_id()
prediction_log = prepare_prediction_log(
    picks,
    season=season,
    pbp_season=pbp_season,
    prediction_run_id=prediction_run_id,
    config=config,
)

if log_predictions:
    import mlflow

    mlflow.set_experiment(mlflow_experiment)
    with mlflow.start_run(run_name=f"predictions_{season}_wk{target_week}") as run:
        mlflow_run_id = run.info.run_id
        prediction_log["mlflow_run_id"] = mlflow_run_id

        mlflow.log_params(
            {
                "season": season,
                "week": target_week,
                "pbp_season": pbp_season,
                "n_simulations": n_simulations,
                "market_blend": market_blend,
                "pick_threshold": pick_threshold,
                "prediction_run_id": prediction_run_id,
            }
        )
        mlflow.log_metrics(
            {
                "games_predicted": float(len(prediction_log)),
                "avg_spread_confidence": float(
                    prediction_log["spread_confidence"].mean()
                ),
                "avg_total_confidence": float(prediction_log["total_confidence"].mean()),
                "high_conf_spread_picks": float(
                    (
                        prediction_log["spread_confidence"] >= pick_threshold
                    ).sum()
                ),
                "high_conf_total_picks": float(
                    (prediction_log["total_confidence"] >= pick_threshold).sum()
                ),
            }
        )
        mlflow.set_tag("prediction_run_id", prediction_run_id)
        mlflow.set_tag("predictions_table", predictions_table)

        artifact_path = f"/tmp/monte_carlo_predictions_{prediction_run_id}.csv"
        prediction_log.to_csv(artifact_path, index=False)
        mlflow.log_artifact(artifact_path)

        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
        (
            pandas_to_spark(spark, prediction_log)
            .write.format("delta")
            .mode("append")
            .option("mergeSchema", "true")
            .saveAsTable(predictions_table)
        )

        print(f"Logged {len(prediction_log)} predictions")
        print(f"prediction_run_id: {prediction_run_id}")
        print(f"mlflow_run_id: {mlflow_run_id}")
        print(f"delta table: {predictions_table}")
else:
    print("log_predictions=false; skipped Delta + MLflow write")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Email predictions (optional)
# MAGIC Sends an HTML table of picks via SendGrid. Requires secrets in scope `nfl`:
# MAGIC `sendgrid_api_key` and `sendgrid_from_email` (verified sender).

# COMMAND ----------

if send_email and notify_email:
    import os

    api_key = ""
    from_email = ""
    try:
        api_key = dbutils.secrets.get(scope="nfl", key="sendgrid_api_key").strip()
    except Exception:
        api_key = (
            os.environ.get("SENDGRID_API_KEY")
            or os.environ.get("sendgrid_api_key")
            or ""
        ).strip()

    try:
        from_email = dbutils.secrets.get(scope="nfl", key="sendgrid_from_email").strip()
    except Exception:
        from_email = (
            os.environ.get("SENDGRID_FROM_EMAIL")
            or os.environ.get("SENDGRID_FROM")
            or notify_email
        ).strip()

    if not api_key:
        print(
            "Email skipped: set sendgrid_api_key in the nfl secret scope "
            "(or SENDGRID_API_KEY in the environment)."
        )
    elif not from_email:
        print("Email skipped: no sendgrid_from_email secret or notify_email fallback.")
    else:
        run_page_url = None
        try:
            ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
            host = ctx.browserHostName().get()
            run_id = ctx.currentRunId().get()
            if run_id and run_id.get() > 0:
                run_page_url = f"https://{host}/#job/run/{run_id.get()}"
        except Exception:
            run_page_url = None

        email_body = format_predictions_email_html(
            prediction_log if log_predictions else picks,
            season=season,
            week=target_week,
            prediction_run_id=prediction_run_id,
            run_page_url=run_page_url,
        )
        subject = f"NFL Monte Carlo picks — {season} Week {target_week}"
        try:
            send_email_sendgrid(
                api_key=api_key,
                to_email=notify_email,
                subject=subject,
                html_content=email_body,
                from_email=from_email,
            )
            print(f"Emailed picks to {notify_email}")
        except Exception as exc:
            print(
                "Email failed from serverless compute (external APIs are often blocked). "
                "Predictions are still logged to Delta. Run locally:\n"
                f"  python scripts/email_weekly_picks.py --week {target_week} "
                f"--to {notify_email}\n"
                f"Error: {exc}"
            )
elif send_email:
    print("send_email=true but notify_email is blank; skipped email")
else:
    print("send_email=false; skipped email")