"""Statistical outlier detection for numeric columns (z-score method)."""

import pandas as pd

MIN_VALUES = 5     # too few values make a standard deviation meaningless
MAX_EXAMPLES = 5   # extreme values listed per column


def _is_row_id(values: pd.Series) -> bool:
    """A whole-number column in which every value differs (1, 2, 3, ...) is a row ID.

    IDs are never "unusual", so flagging them would only add noise.
    """
    return bool((values % 1 == 0).all() and values.is_unique and len(values) > 1)


def find_outliers(df: pd.DataFrame, z_threshold: float = 3.0) -> list[dict]:
    """Flag values further than `z_threshold` standard deviations from their column mean.

    These are prompts for a human to look, not confirmed errors.
    """
    findings = []

    for name in df.select_dtypes(include="number").columns:
        values = df[name].dropna()
        if len(values) < MIN_VALUES or values.std() == 0 or _is_row_id(values):
            continue

        mean, spread = values.mean(), values.std()
        distance = ((values - mean) / spread).abs()
        flagged = distance > z_threshold
        if not flagged.any():
            continue

        outliers = values[flagged]
        most_extreme_first = outliers.loc[distance[flagged].sort_values(ascending=False).index]
        findings.append({
            "column": name,
            "outlier_count": int(flagged.sum()),
            "outlier_pct": round(100 * flagged.sum() / len(values), 2),
            "min_outlier": float(outliers.min()),
            "max_outlier": float(outliers.max()),
            "example_values": [float(v) for v in most_extreme_first.head(MAX_EXAMPLES)],
            "typical_range": [
                round(float(mean - z_threshold * spread), 2),
                round(float(mean + z_threshold * spread), 2),
            ],
        })

    return findings
