# Databricks notebook source
# MAGIC %md
# MAGIC # Monte Carlo weekly accuracy
# MAGIC Grade logged predictions against final scores after a week completes.
# MAGIC Run this on **Tuesday** (or anytime after games finish) to measure ATS and total accuracy.
# MAGIC
# MAGIC **Reads:** `workspace.nfl.monte_carlo_predictions`, `workspace.nfl.nflverse_schedule`
# MAGIC **Writes:** `workspace.nfl.monte_carlo_prediction_grades`
# MAGIC **Logs:** accuracy metrics to MLflow

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace", "Unity Catalog")
dbutils.widgets.text("schema", "nfl", "Schema")
dbutils.widgets.text("season", "2026", "Season to grade")
dbutils.widgets.text("target_week", "", "Week to grade (blank = latest completed)")
dbutils.widgets.text(
    "prediction_run_id",
    "",
    "Prediction run ID (blank = latest for week)",
)
dbutils.widgets.text(
    "mlflow_experiment",
    "/Shared/nfl_monte_carlo",
    "MLflow experiment path",
)
dbutils.widgets.dropdown(
    "log_grades",
    "true",
    ["true", "false"],
    "Append grades to Delta + MLflow",
)

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
season = int(dbutils.widgets.get("season"))
target_week_raw = dbutils.widgets.get("target_week").strip()
prediction_run_id_raw = dbutils.widgets.get("prediction_run_id").strip()
mlflow_experiment = dbutils.widgets.get("mlflow_experiment").strip()
log_grades = dbutils.widgets.get("log_grades").lower() == "true"

predictions_table = f"{catalog}.{schema}.monte_carlo_predictions"
grades_table = f"{catalog}.{schema}.monte_carlo_prediction_grades"
schedule_table = f"{catalog}.{schema}.nflverse_schedule"

print(f"Predictions: {predictions_table}")
print(f"Grades:      {grades_table}")
print(f"Schedule:    {schedule_table}")

# COMMAND ----------

import pandas as pd

from nfl_odds.simulation import (
    filter_ungraded_predictions,
    grade_predictions,
    infer_latest_completed_week,
    select_latest_prediction_run,
    summarize_prediction_accuracy,
)
from nfl_odds.spark_io import pandas_to_spark

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load predictions and results

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

predictions_pdf = spark.table(predictions_table).toPandas()
schedule_pdf = spark.table(schedule_table).toPandas()

if predictions_pdf.empty:
    raise ValueError(
        f"No predictions found in {predictions_table}. "
        "Run monte_carlo_weekly_picks with log_predictions=true first."
    )

if "season" in schedule_pdf.columns:
    schedule_pdf = schedule_pdf[schedule_pdf["season"] == season].copy()

if target_week_raw:
    target_week = int(target_week_raw)
else:
    target_week = infer_latest_completed_week(schedule_pdf, season=season)

if target_week is None:
    raise ValueError(
        "No completed week found in schedule. Set target_week explicitly."
    )

print(f"Grading week {target_week}")

week_predictions = predictions_pdf[
    (predictions_pdf["season"] == season) & (predictions_pdf["week"] == target_week)
].copy()
if week_predictions.empty:
    raise ValueError(f"No predictions found for season={season}, week={target_week}")

if prediction_run_id_raw:
    prediction_run_id = prediction_run_id_raw
else:
    prediction_run_id = select_latest_prediction_run(
        week_predictions,
        season=season,
        week=target_week,
    )

if not prediction_run_id:
    raise ValueError("Could not resolve prediction_run_id for this week.")

run_predictions = week_predictions[
    week_predictions["prediction_run_id"] == prediction_run_id
].copy()
print(f"Grading prediction_run_id: {prediction_run_id}")
print(f"Prediction rows: {len(run_predictions)}")

try:
    existing_grades_pdf = spark.table(grades_table).toPandas()
except Exception:
    existing_grades_pdf = pd.DataFrame()

pending_predictions = filter_ungraded_predictions(run_predictions, existing_grades_pdf)
if pending_predictions.empty:
    print("All predictions for this run are already graded.")
    graded = existing_grades_pdf[
        existing_grades_pdf["prediction_run_id"] == prediction_run_id
    ].copy()
else:
    graded = grade_predictions(pending_predictions, schedule_pdf)
    if graded.empty:
        raise ValueError(
            f"No completed games with scores found for week {target_week}. "
            "Ensure nflverse_schedule has final scores before grading."
        )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Accuracy summary

# COMMAND ----------

metrics = summarize_prediction_accuracy(graded)
print("Accuracy metrics:")
for key, value in sorted(metrics.items()):
    if key.endswith("accuracy"):
        print(f"  {key}: {value * 100:.1f}%")
    else:
        print(f"  {key}: {value}")

summary = graded[
    [
        "game_id",
        "away_abbr",
        "home_abbr",
        "spread_pick",
        "spread_confidence",
        "actual_spread_result",
        "spread_correct",
        "total_pick",
        "total_confidence",
        "actual_total_result",
        "total_correct",
        "actual_away_score",
        "actual_home_score",
        "actual_total",
        "proj_total",
        "total_error",
    ]
].copy()

display(spark.createDataFrame(summary))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cumulative accuracy (all graded weeks)

# COMMAND ----------

if existing_grades_pdf.empty:
    combined = graded.copy()
else:
    combined = pd.concat([existing_grades_pdf, graded], ignore_index=True)

if not combined.empty:
    combined = combined.drop_duplicates(subset=["prediction_id"], keep="last")
    cumulative = summarize_prediction_accuracy(combined)
    print("Cumulative metrics across all stored grades:")
    for key, value in sorted(cumulative.items()):
        if key.endswith("accuracy"):
            print(f"  {key}: {value * 100:.1f}%")
        else:
            print(f"  {key}: {value}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Log grades (Delta + MLflow)

# COMMAND ----------

if log_grades and not graded.empty and not pending_predictions.empty:
    import mlflow

    mlflow.set_experiment(mlflow_experiment)
    with mlflow.start_run(run_name=f"accuracy_{season}_wk{target_week}") as run:
        mlflow.log_params(
            {
                "season": season,
                "week": target_week,
                "prediction_run_id": prediction_run_id,
                "graded_games": len(graded),
            }
        )
        mlflow.log_metrics(metrics)
        mlflow.set_tag("prediction_run_id", prediction_run_id)
        mlflow.set_tag("grades_table", grades_table)

        artifact_path = f"/tmp/monte_carlo_grades_{prediction_run_id}.csv"
        graded.to_csv(artifact_path, index=False)
        mlflow.log_artifact(artifact_path)

        (
            pandas_to_spark(spark, graded)
            .write.format("delta")
            .mode("append")
            .option("mergeSchema", "true")
            .saveAsTable(grades_table)
        )

        print(f"Appended {len(graded)} rows to {grades_table}")
        print(f"mlflow_run_id: {run.info.run_id}")
elif pending_predictions.empty:
    print("Skipped grade write; nothing new to append.")
else:
    print("log_grades=false; skipped Delta + MLflow write")