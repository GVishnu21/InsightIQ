"""Choose a chart for a query result and build it with Plotly.

The chart type is picked by simple, explainable rules based on the SHAPE of the
result (which columns are dates, categories or numbers), not by the AI. That
keeps it predictable, testable and free of invented values: every point drawn
comes straight from the DuckDB result.

The function returns the figure as plain JSON (`{"data": [...], "layout": {...}}`);
the React app renders it with Plotly.js.

Rules, first match wins:
    1 date + number(s)                       -> line  (one line per category if there is one)
    2 category + number, share-style question
      with 2-6 positive values               -> pie
    3 category + number(s)                   -> bar   (grouped for several numbers)
    4 two categories + one number            -> grouped bar
    5 two numbers, no category               -> scatter
    6 one number, many rows                  -> bar chart of a 10-bin histogram
    otherwise (single value, no numbers...)  -> no chart
"""

import json
import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from profiler import friendly_type

logger = logging.getLogger("insightiq")

MAX_CATEGORIES = 25        # bars/pie slices drawn; the SQL's ORDER BY decides which
MAX_MEASURES = 3           # numeric columns drawn together
MAX_GROUPED_ROWS = 60      # two-category grouped bars get unreadable beyond this
PIE_MAX_SLICES = 6
MIN_HISTOGRAM_ROWS = 8
SHARE_WORDS = ("share", "proportion", "percent", "breakdown", "distribution", "composition", "split")


def _label(column: str) -> str:
    return str(column).replace("_", " ").strip().capitalize()


def _classify(df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    """Split columns into (dates, categories, numbers). Empty columns are ignored."""
    dates, categories, numbers = [], [], []
    for col in df.columns:
        series = df[col]
        if series.dropna().empty:
            continue
        kind = friendly_type(series)
        if kind == "numeric":
            numbers.append(col)
        elif kind == "date":
            dates.append(col)
        elif kind in ("text", "boolean"):
            categories.append(col)
    return dates, categories, numbers


def _to_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str), errors="coerce", format="mixed")


def _finish(fig: go.Figure, title: str, chart_type: str, x_title: str = "", y_title: str = "") -> dict:
    fig.update_layout(
        template=None,  # keeps the JSON small; the app styles it
        title={"text": title[:90]},
        height=400,
        margin={"l": 60, "r": 20, "t": 60, "b": 60},
        xaxis={"title": {"text": x_title}},
        yaxis={"title": {"text": y_title}},
        legend={"orientation": "h", "y": -0.25},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    # to_json (not to_dict) converts every value to plain JSON types.
    return {"type": chart_type, "figure": json.loads(fig.to_json())}


def _floats(series: pd.Series) -> list:
    return [None if pd.isna(v) else float(v) for v in series]


def _line_chart(df, date_col, categories, numbers, title):
    work = df.copy()
    work["_when"] = _to_dates(work[date_col])
    work = work.dropna(subset=["_when"]).sort_values("_when")
    if len(work["_when"].unique()) < 2:
        return None

    fig = go.Figure()
    category = categories[0] if len(categories) == 1 and len(numbers) == 1 else None
    if category:
        for name, part in work.groupby(category):
            fig.add_trace(go.Scatter(x=part["_when"].dt.strftime("%Y-%m-%d").tolist(),
                                     y=_floats(part[numbers[0]]), mode="lines+markers", name=str(name)))
        y_title = _label(numbers[0])
    else:
        for col in numbers[:MAX_MEASURES]:
            fig.add_trace(go.Scatter(x=work["_when"].dt.strftime("%Y-%m-%d").tolist(),
                                     y=_floats(work[col]), mode="lines+markers", name=_label(col)))
        y_title = _label(numbers[0]) if len(numbers) == 1 else ""
    fig.update_xaxes(type="date")
    if (work["_when"].dt.day == 1).all():
        # Monthly data (every date is the 1st): label by month, not by arbitrary 2-week ticks.
        fig.update_xaxes(tickformat="%b %Y", dtick="M1")
    return _finish(fig, title, "line", _label(date_col), y_title)


def _bar_or_pie(df, category, numbers, question, title):
    shown = df.head(MAX_CATEGORIES)
    suffix = f" (first {MAX_CATEGORIES} of {len(df)})" if len(df) > MAX_CATEGORIES else ""
    labels = shown[category].fillna("(missing)").astype(str).tolist()
    values = shown[numbers[0]]

    wants_share = any(word in question.lower() for word in SHARE_WORDS)
    if (len(numbers) == 1 and wants_share and 2 <= len(shown) <= PIE_MAX_SLICES
            and len(df) == len(shown) and (values.dropna() > 0).all()):
        fig = go.Figure(go.Pie(labels=labels, values=_floats(values), hole=0.35, sort=False))
        return _finish(fig, title, "pie")

    fig = go.Figure()
    for col in numbers[:MAX_MEASURES]:
        fig.add_trace(go.Bar(x=labels, y=_floats(shown[col]), name=_label(col)))
    fig.update_layout(barmode="group", showlegend=len(numbers) > 1)
    y_title = _label(numbers[0]) if len(numbers) == 1 else ""
    return _finish(fig, title + suffix, "bar", _label(category), y_title)


def _grouped_bar(df, first, second, number, title):
    if len(df) > MAX_GROUPED_ROWS:
        return None
    fig = go.Figure()
    for name, part in df.groupby(second):
        fig.add_trace(go.Bar(x=part[first].fillna("(missing)").astype(str).tolist(),
                             y=_floats(part[number]), name=str(name)))
    fig.update_layout(barmode="group")
    return _finish(fig, title, "bar", _label(first), _label(number))


def _scatter(df, x_col, y_col, title):
    work = df[[x_col, y_col]].dropna()
    if len(work) < 3:
        return None
    fig = go.Figure(go.Scatter(x=_floats(work[x_col]), y=_floats(work[y_col]), mode="markers"))
    return _finish(fig, title, "scatter", _label(x_col), _label(y_col))


def _histogram(df, number, title):
    values = df[number].dropna().to_numpy(dtype=float)
    if values.size < MIN_HISTOGRAM_ROWS or values.min() == values.max():
        return None
    counts, edges = np.histogram(values, bins=10)
    labels = [f"{edges[i]:,.4g} to {edges[i + 1]:,.4g}" for i in range(len(counts))]
    fig = go.Figure(go.Bar(x=labels, y=counts.tolist()))
    fig.update_layout(bargap=0.05)
    return _finish(fig, title, "histogram", _label(number), "Number of rows")


def build_chart(df: pd.DataFrame, question: str = "") -> dict | None:
    """Return {"type": ..., "figure": {...}} for the result, or None if no chart fits.

    Never raises: a chart is a bonus, and a failure here must not break the answer.
    """
    try:
        if df.empty or len(df) < 2:
            return None  # one row is a single fact, not a chart

        dates, categories, numbers = _classify(df)
        if not numbers:
            return None
        title = question.strip().rstrip("?") or "Query result"

        if dates:
            return _line_chart(df, dates[0], categories, numbers, title)
        if len(categories) == 1:
            return _bar_or_pie(df, categories[0], numbers, question, title)
        if len(categories) == 2 and len(numbers) == 1:
            return _grouped_bar(df, categories[0], categories[1], numbers[0], title)
        if not categories and len(numbers) >= 2:
            return _scatter(df, numbers[0], numbers[1], title)
        if not categories and len(numbers) == 1:
            return _histogram(df, numbers[0], title)
        return None
    except Exception:
        logger.exception("Chart generation failed")
        return None
