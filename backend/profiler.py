"""Dataset profiling: the facts shown on the overview screen and used by the summary.

Everything here is plain Pandas/NumPy arithmetic. No AI is involved, so these
numbers can be trusted and are reused wherever the app needs facts about a file.
"""

import numpy as np
import pandas as pd

MAX_DUPLICATE_EXAMPLES = 10
DATE_SAMPLE_SIZE = 50
DATE_PARSE_THRESHOLD = 0.9  # share of sampled values that must parse as dates


def _round(value, places: int = 2):
    """Plain float for JSON; missing values become None because JSON has no NaN."""
    return None if pd.isna(value) else round(float(value), places)


def friendly_type(series: pd.Series) -> str:
    """Label a column numeric / boolean / date / text.

    Pandas reports dates read from a CSV as plain strings, which tells the reader
    nothing, so text columns are tested for date-like content.
    """
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"

    present = series.dropna().astype(str)
    if present.empty:
        return "text"

    sample = present.head(DATE_SAMPLE_SIZE)
    # Requiring a digit and a separator keeps words such as "May" from counting as dates.
    if sample.str.contains(r"\d").all() and sample.str.contains(r"[-/:]").all():
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        if parsed.notna().mean() >= DATE_PARSE_THRESHOLD:
            return "date"
    return "text"


def _column_overview(df: pd.DataFrame) -> list[dict]:
    row_count = len(df)
    missing = df.isna().sum()
    distinct = df.nunique()
    overview = []
    for name in df.columns:
        gaps = int(missing[name])
        overview.append({
            "column": name,
            "dtype": str(df[name].dtype),
            "type": friendly_type(df[name]),
            "missing": gaps,
            "missing_pct": round(100 * gaps / row_count, 2) if row_count else 0.0,
            "unique_values": int(distinct[name]),
        })
    return overview


def _numeric_statistics(series: pd.Series) -> dict:
    values = series.dropna().to_numpy(dtype=float)
    stats = dict.fromkeys(
        ["column", "count", "min", "q25", "median", "q75", "max", "mean", "std", "missing"]
    )
    stats["column"] = series.name
    stats["count"] = int(values.size)
    stats["missing"] = int(series.isna().sum())
    if values.size:
        q25, median, q75 = np.percentile(values, [25, 50, 75])
        stats.update(
            min=_round(values.min()), q25=_round(q25), median=_round(median),
            q75=_round(q75), max=_round(values.max()), mean=_round(values.mean()),
            std=_round(values.std(ddof=1)) if values.size > 1 else None,
        )
    return stats


def _duplicate_report(df: pd.DataFrame) -> tuple[int, list[dict]]:
    """Rows identical to an EARLIER row (the first copy is not a duplicate)."""
    repeated = df[df.duplicated()]
    examples = [
        {"row": int(position) + 1, **values}  # 1-based data row, header excluded
        for position, values in repeated.head(MAX_DUPLICATE_EXAMPLES)
        .fillna("")
        .to_dict(orient="index")
        .items()
    ]
    return len(repeated), examples


def profile_dataset(df: pd.DataFrame) -> dict:
    overview = _column_overview(df)
    duplicate_count, duplicate_examples = _duplicate_report(df)

    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "total_missing": int(df.isna().sum().sum()),
        "duplicate_rows": duplicate_count,
        "duplicate_samples": duplicate_examples,
        "columns_summary": overview,
        "missing_columns": [
            {"column": c["column"], "missing_count": c["missing"], "missing_pct": c["missing_pct"]}
            for c in overview
            if c["missing"] > 0
        ],
        "numeric_summary": [
            _numeric_statistics(df[name]) for name in df.select_dtypes(include="number").columns
        ],
    }
