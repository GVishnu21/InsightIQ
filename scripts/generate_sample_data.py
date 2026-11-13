"""Generate sample-data/retail_orders.csv, a synthetic retail dataset for demos and tests.

Run from the project root:   python scripts/generate_sample_data.py

The data is random (fixed seed, so the file is reproducible) but deliberately
contains the situations the app is built to handle:
  * a few missing values in several columns
  * two exact duplicate rows
  * three unusually large enterprise orders (outliers)
  * one product category whose share of orders declines over the six months
  * a few orders with negative margin
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
ORDER_COUNT = 180
OUTPUT = Path(__file__).resolve().parent.parent / "sample-data" / "retail_orders.csv"

REGIONS = ["North", "South", "East", "West", "Central"]
REGION_WEIGHTS = [0.22, 0.18, 0.20, 0.25, 0.15]
CHANNELS = ["Online", "Retail Store", "Partner", "Wholesale"]
SEGMENTS = ["Consumer", "Small Business", "Enterprise"]
DISCOUNTS = [0.0, 0.05, 0.10, 0.15, 0.20]

# category: (min price, max price, max units per order, margin rate)
CATEGORIES = {
    "Laptops": (900, 1500, 5, 0.18),
    "Phones": (400, 900, 6, 0.22),
    "Tablets": (250, 600, 6, 0.20),
    "Monitors": (150, 450, 8, 0.15),
    "Accessories": (15, 80, 25, 0.40),
}


def category_weights(month_index: int) -> list[float]:
    """Accessories fade over the months while phones and laptops grow."""
    weights = {
        "Laptops": 0.18 + 0.02 * month_index,
        "Phones": 0.20 + 0.03 * month_index,
        "Tablets": 0.17,
        "Monitors": 0.13,
        "Accessories": 0.32 - 0.05 * month_index,
    }
    total = sum(weights.values())
    return [weights[name] / total for name in CATEGORIES]


def build_orders(rng: np.random.Generator) -> pd.DataFrame:
    days = np.sort(rng.integers(0, 181, ORDER_COUNT))
    dates = pd.Timestamp("2025-01-01") + pd.to_timedelta(days, unit="D")

    rows = []
    for date in dates:
        category = rng.choice(list(CATEGORIES), p=category_weights(date.month - 1))
        low, high, max_units, margin_rate = CATEGORIES[category]
        unit_price = int(round(rng.uniform(low, high) / 5) * 5)
        units = int(rng.integers(1, max_units + 1))
        discount = float(rng.choice(DISCOUNTS))
        revenue = round(units * unit_price * (1 - discount), 2)
        rows.append({
            "order_date": date.strftime("%Y-%m-%d"),
            "region": rng.choice(REGIONS, p=REGION_WEIGHTS),
            "category": category,
            "channel": rng.choice(CHANNELS),
            "customer_segment": rng.choice(SEGMENTS, p=[0.5, 0.3, 0.2]),
            "units": units,
            "unit_price": unit_price,
            "discount": discount,
            "revenue": revenue,
            "margin": round(revenue * margin_rate * rng.uniform(0.7, 1.15), 2),
        })
    return pd.DataFrame(rows)


def add_quirks(orders: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    # Three unusually large enterprise laptop orders.
    for position in rng.choice(len(orders), 3, replace=False):
        units = int(rng.integers(60, 91))
        price = int(orders.at[position, "unit_price"]) if orders.at[position, "category"] == "Laptops" else 1200
        orders.loc[position, ["category", "customer_segment", "units", "unit_price", "discount"]] = [
            "Laptops", "Enterprise", units, price, 0.15,
        ]
        orders.at[position, "revenue"] = round(units * price * 0.85, 2)
        orders.at[position, "margin"] = round(orders.at[position, "revenue"] * 0.17, 2)

    # A few loss-making orders.
    for position in rng.choice(len(orders), 3, replace=False):
        orders.at[position, "margin"] = -round(abs(orders.at[position, "margin"]) * 0.6 + 20, 2)

    # Missing values.
    for column, count in {"region": 5, "channel": 6, "customer_segment": 4,
                          "discount": 4, "revenue": 3, "margin": 3}.items():
        orders[column] = orders[column].astype(object)
        orders.loc[rng.choice(len(orders), count, replace=False), column] = None

    # Two exact duplicate rows, inserted away from their originals.
    for source in rng.choice(len(orders), 2, replace=False):
        copy = orders.iloc[[source]]
        spot = int(rng.integers(0, len(orders)))
        orders = pd.concat([orders.iloc[:spot], copy, orders.iloc[spot:]], ignore_index=True)

    return orders


def main() -> None:
    rng = np.random.default_rng(SEED)
    orders = add_quirks(build_orders(rng), rng)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    orders.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(orders)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
