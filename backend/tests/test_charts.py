import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from charts import MAX_CATEGORIES, build_chart  # noqa: E402


def chart_type(df, question=""):
    chart = build_chart(df, question)
    return None if chart is None else chart["type"]


def traces(df, question=""):
    return build_chart(df, question)["figure"]["data"]


REGIONS = pd.DataFrame({"region": ["Central", "West", "North"], "total_sales": [115073.5, 86959.5, 77028.0]})
CHANNELS = pd.DataFrame({"sales_channel": ["Online", "Retail", "Partner", "Wholesale"],
                         "total_sales": [204032.0, 90952.5, 80774.0, 27653.0]})
MONTHS = pd.DataFrame({"month": ["2024-01", "2024-02", "2024-03", "2024-04"], "total_sales": [10.0, 20.0, 15.0, 30.0]})


# ------------------------------------------------------------ chart choice

def test_category_plus_number_is_a_bar_chart():
    assert chart_type(REGIONS, "Which region has the highest revenue?") == "bar"


def test_share_style_question_with_few_positive_categories_is_a_pie():
    assert chart_type(CHANNELS, "Show the revenue distribution by sales channel.") == "pie"
    assert chart_type(CHANNELS, "revenue by sales channel") == "bar"  # no share wording


def test_pie_is_avoided_when_values_are_negative_or_too_many():
    negative = CHANNELS.assign(total_sales=[10.0, -5.0, 3.0, 2.0])
    assert chart_type(negative, "revenue distribution") == "bar"
    many = pd.DataFrame({"c": list("abcdefgh"), "v": range(1, 9)})
    assert chart_type(many, "distribution of v") == "bar"


def test_date_plus_number_is_a_line_chart_sorted_by_time():
    shuffled = MONTHS.iloc[[2, 0, 3, 1]]
    data = traces(shuffled, "sales by month")
    assert chart_type(shuffled) == "line"
    assert data[0]["x"] == ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]
    assert data[0]["y"] == [10.0, 20.0, 15.0, 30.0]


def test_monthly_series_gets_month_ticks_but_daily_series_does_not():
    assert build_chart(MONTHS, "q")["figure"]["layout"]["xaxis"]["dtick"] == "M1"
    daily = pd.DataFrame({"day": ["2024-01-05", "2024-01-06", "2024-01-09"], "n": [1.0, 2.0, 3.0]})
    assert "dtick" not in build_chart(daily, "q")["figure"]["layout"]["xaxis"]


def test_date_category_number_draws_one_line_per_category():
    df = pd.DataFrame({
        "month": ["2024-01", "2024-02", "2024-01", "2024-02"],
        "product": ["Phone", "Phone", "Laptop", "Laptop"],
        "sales": [1.0, 2.0, 3.0, 4.0],
    })
    data = traces(df, "monthly sales by product")
    assert {t["name"] for t in data} == {"Phone", "Laptop"}


def test_two_categories_and_a_number_is_a_grouped_bar():
    df = pd.DataFrame({"region": ["N", "N", "S", "S"], "channel": ["Web", "Shop", "Web", "Shop"], "sales": [1.0, 2.0, 3.0, 4.0]})
    assert chart_type(df) == "bar"
    assert {t["name"] for t in traces(df)} == {"Web", "Shop"}


def test_two_numbers_make_a_scatter_and_one_number_many_rows_a_histogram():
    assert chart_type(pd.DataFrame({"qty": [1.0, 2.0, 3.0, 4.0], "price": [10.0, 20.0, 15.0, 30.0]})) == "scatter"
    values = pd.DataFrame({"sales": [float(i) for i in range(1, 21)]})
    assert chart_type(values) == "histogram"
    assert sum(traces(values)[0]["y"]) == 20  # every row lands in exactly one bin


def test_multiple_measures_become_grouped_bars():
    df = REGIONS.assign(total_profit=[10.0, 20.0, 30.0])
    assert [t["name"] for t in traces(df, "sales and profit by region")] == ["Total sales", "Total profit"]


# ------------------------------------------------------------ no chart cases

@pytest.mark.parametrize("df", [
    pd.DataFrame({"region": ["Central"], "total": [1.0]}),   # a single row is just a fact
    pd.DataFrame({"product": ["a", "b", "c"]}),              # nothing numeric
    pd.DataFrame({"a": []}),                                 # empty
    pd.DataFrame({"sales": [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0]}),  # no spread to bin
    pd.DataFrame({"x": [None, None], "y": [None, None]}),    # only missing values
])
def test_no_chart_when_it_would_not_help(df):
    assert build_chart(df, "q") is None


# ------------------------------------------------------------- data fidelity

def test_chart_values_are_exactly_the_result_values():
    data = traces(REGIONS, "highest revenue")[0]
    assert data["x"] == ["Central", "West", "North"]
    assert data["y"] == [115073.5, 86959.5, 77028.0]


def test_missing_category_gets_a_visible_label_not_a_dropped_bar():
    df = pd.DataFrame({"region": ["N", None, "S"], "total": [1.0, 2.0, 3.0]})
    assert traces(df)[0]["x"] == ["N", "(missing)", "S"]


def test_long_results_are_capped_and_the_title_says_so():
    df = pd.DataFrame({"c": [f"cat{i}" for i in range(40)], "v": [float(i) for i in range(40)]})
    chart = build_chart(df, "all categories")
    assert len(chart["figure"]["data"][0]["x"]) == MAX_CATEGORIES
    assert f"first {MAX_CATEGORIES} of 40" in chart["figure"]["layout"]["title"]["text"]


def test_output_is_plain_small_json_with_no_binary_arrays():
    chart = build_chart(REGIONS, "q")
    text = json.dumps(chart, allow_nan=False)  # raises on NaN / non-JSON types
    assert "bdata" not in text and len(text) < 5000


def test_a_failure_inside_chart_code_returns_none_instead_of_raising(monkeypatch):
    import charts
    monkeypatch.setattr(charts, "_classify", lambda df: 1 / 0)
    assert build_chart(REGIONS, "q") is None
