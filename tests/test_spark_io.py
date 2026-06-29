import pandas as pd

from nfl_odds.spark_io import prepare_pandas_for_spark


def test_prepare_pandas_for_spark_handles_all_null_columns():
    pdf = pd.DataFrame(
        {
            "game_id": ["2025_01_ARI_NO"],
            "empty_col": [pd.NA],
            "player_name": ["K.Murray"],
        }
    )
    prepared = prepare_pandas_for_spark(pdf)
    assert str(prepared["empty_col"].dtype) == "string"
    assert str(prepared["player_name"].dtype) in {"string", "str", "object"}