"""Tests for the SQL safety layers. Run from the backend folder:  pytest

No Gemini calls are made: we feed hand-written "AI outputs" (good and malicious)
straight into the validator and the DuckDB runner.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from query_engine import run_query  # noqa: E402
from sql_validator import SQLValidationError, validate_sql  # noqa: E402

COLUMNS = ["date", "region", "product", "sales", "profit", "updated_at", "Sales Rep"]


@pytest.mark.parametrize("sql", [
    'SELECT "region", SUM("sales") AS total FROM uploaded_data GROUP BY "region"',
    "SELECT region FROM uploaded_data ORDER BY region LIMIT 5;",
    'SELECT "Sales Rep", COUNT(*) AS n FROM uploaded_data GROUP BY "Sales Rep"',
    "SELECT MAX(updated_at) FROM uploaded_data",  # contains 'update' but is a valid column
    "SELECT region, SUM(sales) AS total FROM uploaded_data GROUP BY region ORDER BY total DESC",
    "WITH t AS (SELECT region, sales FROM uploaded_data) SELECT region, SUM(sales) FROM t GROUP BY region",
    "SELECT region FROM uploaded_data UNION SELECT product FROM uploaded_data",
    "SELECT COUNT(*) FROM uploaded_data WHERE sales > (SELECT AVG(sales) FROM uploaded_data)",
])
def test_valid_queries_are_accepted(sql):
    assert validate_sql(sql, COLUMNS)


@pytest.mark.parametrize("sql", [
    "DROP TABLE uploaded_data",
    "DELETE FROM uploaded_data",
    "UPDATE uploaded_data SET sales = 0",
    "INSERT INTO uploaded_data VALUES (1)",
    "CREATE TABLE x AS SELECT * FROM uploaded_data",
    "COPY uploaded_data TO 'out.csv'",
    "ATTACH 'other.db'",
    "PRAGMA database_list",
    "SET enable_external_access = true",
    "SELECT 1; DROP TABLE uploaded_data",
    "SELECT region FROM uploaded_data; SELECT product FROM uploaded_data",
    "",
    "this is not sql at all",
])
def test_dangerous_or_invalid_statements_are_rejected(sql):
    with pytest.raises(SQLValidationError):
        validate_sql(sql, COLUMNS)


@pytest.mark.parametrize("sql", [
    "SELECT * FROM read_csv('C:/Windows/win.ini')",
    "SELECT * FROM read_text('secret.txt')",
    "SELECT * FROM read_parquet('x.parquet')",
    "SELECT * FROM glob('*')",
    "SELECT * FROM 'secret.csv'",
    "SELECT getenv('GEMINI_API_KEY')",
    "SELECT * FROM other_table",
    "SELECT * FROM main.uploaded_data",
    "SELECT no_such_column FROM uploaded_data",
])
def test_data_exfiltration_and_unknown_references_are_rejected(sql):
    with pytest.raises(SQLValidationError):
        validate_sql(sql, COLUMNS)


def test_duckdb_layer_blocks_file_access_even_without_validator(tmp_path):
    """Layer 2: even if a query slipped past layer 1, DuckDB refuses file access."""
    secret = tmp_path / "secret.csv"
    secret.write_text("password\nhunter2\n")  # a real file that DuckDB could read
    df = pd.DataFrame({"region": ["N", "S"], "sales": [1, 2]})
    sql = f"SELECT * FROM read_csv('{secret.as_posix()}')"
    with pytest.raises(Exception, match="(?i)file system operations are disabled"):
        run_query(df, sql)


def test_unprotected_duckdb_could_read_that_file(tmp_path):
    """Proves the test above is meaningful: without the protection the read succeeds."""
    import duckdb

    secret = tmp_path / "secret.csv"
    secret.write_text("password\nhunter2\n")
    rows = duckdb.connect().execute(f"SELECT * FROM read_csv('{secret.as_posix()}')").fetchall()
    assert rows == [("hunter2",)]


def test_run_query_returns_real_results():
    df = pd.DataFrame({"region": ["N", "N", "S"], "sales": [1, 2, 5]})
    result = run_query(df, "SELECT region, SUM(sales) AS total FROM uploaded_data GROUP BY region ORDER BY region")
    assert result.to_dict("records") == [{"region": "N", "total": 3}, {"region": "S", "total": 5}]
