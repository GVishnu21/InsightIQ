import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anomalies import find_outliers  # noqa: E402
from profiler import friendly_type, profile_dataset  # noqa: E402


def test_counts_missing_and_duplicates():
    df = pd.DataFrame({"a": [1, 1, 2, None], "b": ["x", "x", "y", "z"]})
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # exact copy of row 1
    profile = profile_dataset(df)
    assert profile["rows"] == 5
    assert profile["total_missing"] == 1
    # rows 0, 1 and 4 are identical; only the later copies (1 and 4) are duplicates
    assert profile["duplicate_rows"] == 2


def test_duplicate_samples_show_the_repeated_rows():
    df = pd.DataFrame({"a": [1, 2, 1], "b": ["x", "y", "x"]})
    samples = profile_dataset(df)["duplicate_samples"]
    assert samples == [{"row": 3, "a": 1, "b": "x"}]


def test_no_duplicates_gives_empty_sample_list():
    assert profile_dataset(pd.DataFrame({"a": [1, 2, 3]}))["duplicate_samples"] == []


def test_numeric_statistics_match_numpy():
    values = [1, 2, 3, 4, 100]
    stats = profile_dataset(pd.DataFrame({"n": values}))["numeric_summary"][0]
    assert stats["count"] == 5
    assert stats["min"] == 1 and stats["max"] == 100
    assert stats["median"] == 3
    assert stats["q25"] == 2 and stats["q75"] == 4
    assert stats["mean"] == round(float(np.mean(values)), 2)
    assert stats["std"] == round(float(np.std(values, ddof=1)), 2)


def test_all_missing_and_single_value_columns_do_not_produce_nan():
    df = pd.DataFrame({"empty": [None, None], "one": [5.0, None]})
    profile = profile_dataset(df)
    json.dumps(profile, allow_nan=False)  # raises if any NaN slipped through
    one = next(s for s in profile["numeric_summary"] if s["column"] == "one")
    assert one["std"] is None and one["mean"] == 5.0


def test_friendly_types():
    assert friendly_type(pd.Series([1, 2, 3])) == "numeric"
    assert friendly_type(pd.Series([True, False])) == "boolean"
    assert friendly_type(pd.Series(["2024-01-01", "2024-02-15", "2024-03-30"])) == "date"
    assert friendly_type(pd.Series(["01/02/2024", "03/04/2024"])) == "date"
    assert friendly_type(pd.Series(["North", "South", "May"])) == "text"
    assert friendly_type(pd.Series([None, None], dtype="object")) == "text"


def test_anomalies_report_actual_values_most_extreme_first():
    df = pd.DataFrame({"v": [10.0] * 60 + [600.0, 900.0]})  # listed least extreme first
    result = find_outliers(df)
    assert len(result) == 1
    entry = result[0]
    assert entry["column"] == "v"
    assert entry["outlier_count"] == 2
    assert entry["example_values"] == [900.0, 600.0]  # most extreme first
    assert entry["min_outlier"] == 600.0 and entry["max_outlier"] == 900.0
    assert entry["outlier_pct"] == round(2 / 62 * 100, 2)
    assert entry["typical_range"][0] < 10 < entry["typical_range"][1]


def test_id_like_columns_are_not_flagged():
    df = pd.DataFrame({"id": range(1, 31), "v": [1.0] * 29 + [1000.0]})
    flagged = [entry["column"] for entry in find_outliers(df)]
    assert "id" not in flagged
    assert "v" in flagged


def test_sample_dataset_profile_is_json_safe_and_shows_the_planted_quirks():
    sample = Path(__file__).resolve().parents[2] / "sample-data" / "retail_orders.csv"
    df = pd.read_csv(sample)
    profile = profile_dataset(df)
    json.dumps(profile, allow_nan=False)
    json.dumps(find_outliers(df), allow_nan=False)

    types = {c["column"]: c["type"] for c in profile["columns_summary"]}
    assert types["order_date"] == "date" and types["region"] == "text" and types["revenue"] == "numeric"
    assert profile["duplicate_rows"] == 2
    assert profile["total_missing"] > 0
    assert {"units", "revenue"} <= {entry["column"] for entry in find_outliers(df)}
