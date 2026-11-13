"""Run validated SQL on an uploaded DataFrame with DuckDB.

This is layer 2 of SQL safety (layer 1 is sql_validator.py). The connection is
created fresh for every query, is in-memory only, and has external access
turned off, so queries cannot read or write files on the server.
"""

import duckdb
import pandas as pd

from sql_validator import TABLE_NAME

MAX_ROWS = 1000  # hard cap on rows pulled back, whatever the query asks for


def run_query(df: pd.DataFrame, sql: str) -> pd.DataFrame:
    """Execute already-validated SQL against df, exposed as table `uploaded_data`."""
    connection = duckdb.connect(
        database=":memory:",
        config={"enable_external_access": False},
    )
    try:
        connection.register(TABLE_NAME, df)
        # Locking stops a query from switching the protection back on or off.
        connection.execute("SET lock_configuration = true")
        return connection.execute(sql).df().head(MAX_ROWS)
    finally:
        connection.close()
