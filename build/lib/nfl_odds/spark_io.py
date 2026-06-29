"""Helpers for writing pandas DataFrames to Spark on serverless."""

from __future__ import annotations

import pandas as pd


def prepare_pandas_for_spark(pdf: pd.DataFrame) -> pd.DataFrame:
    """Coerce ambiguous pandas dtypes so Spark Connect can infer a schema."""
    frame = pdf.copy()

    for column in frame.columns:
        series = frame[column]
        if series.isna().all():
            frame[column] = series.astype("string")
        elif series.dtype == object:
            frame[column] = series.astype("string")
        elif pd.api.types.is_datetime64_any_dtype(series.dtype):
            frame[column] = pd.to_datetime(series, utc=True, errors="coerce")

    return frame


def pandas_to_spark(spark, pdf: pd.DataFrame):
    prepared = prepare_pandas_for_spark(pdf)
    return spark.createDataFrame(prepared)