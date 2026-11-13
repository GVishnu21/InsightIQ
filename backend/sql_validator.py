"""Validate AI-generated SQL *before* it touches the database.

The model's output is untrusted text. Instead of searching it for bad words
(which wrongly blocks a column like "updated_at" and misses tricks), we PARSE
it into a syntax tree with sqlglot and check the structure:

  1. exactly one statement
  2. it is a SELECT (a UNION of SELECTs and WITH ... SELECT are fine)
  3. no write/DDL/admin nodes anywhere inside it
  4. only the uploaded table (or a CTE defined in the query) is read from
  5. no table-valued functions such as read_csv('C:/secret.csv')
  6. no dangerous functions (environment/file access)
  7. every column exists in the dataset (or is an alias made by the query)

This is layer 1. Layer 2 lives in query_engine.py: DuckDB itself is started
with external file access disabled, so even a missed trick cannot read files.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

TABLE_NAME = "uploaded_data"

# Statement/clause types that must never appear anywhere in the query tree.
FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge,
    exp.Create, exp.Drop, exp.Alter, exp.TruncateTable,
    exp.Copy, exp.Attach, exp.Detach, exp.Pragma, exp.Set,
    exp.Command, exp.Use, exp.Transaction, exp.Commit, exp.Rollback,
)

# Functions that reach outside the dataset (files, environment, extensions).
FORBIDDEN_FUNCTIONS = {
    "getenv", "glob", "load", "install", "query", "query_table",
    "current_setting", "duckdb_settings", "pragma_database_list",
}
FORBIDDEN_FUNCTION_PREFIXES = ("read_", "write_", "parquet_", "sniff_", "iceberg_", "delta_")


class SQLValidationError(ValueError):
    """Raised when generated SQL is rejected. The message is safe to show users."""


def validate_sql(sql: str, columns: list[str]) -> str:
    """Return the cleaned SQL if it is safe, otherwise raise SQLValidationError."""
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        raise SQLValidationError("The model returned an empty query.")

    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except SqlglotError as exc:
        raise SQLValidationError(f"The generated SQL could not be parsed: {exc}") from exc

    if len(statements) != 1:
        raise SQLValidationError("Only a single SQL statement is allowed.")
    tree = statements[0]

    if not isinstance(tree, (exp.Select, exp.Union)):
        raise SQLValidationError("Only read-only SELECT queries are allowed.")

    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SQLValidationError(f"Forbidden operation: {type(node).__name__}.")

    _check_tables(tree)
    _check_functions(tree)
    _check_columns(tree, columns)
    return sql


def _check_tables(tree: exp.Expression) -> None:
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    allowed = {TABLE_NAME} | cte_names
    for table in tree.find_all(exp.Table):
        # read_csv('file') etc. parse as a Table whose "this" is a function, not a name.
        if not isinstance(table.this, exp.Identifier):
            raise SQLValidationError("Table functions (like read_csv) are not allowed.")
        if table.db or table.catalog:
            raise SQLValidationError("Schema-qualified tables are not allowed.")
        if table.name.lower() not in allowed:
            raise SQLValidationError(
                f"Unknown table '{table.name}'. Only '{TABLE_NAME}' can be queried."
            )


def _check_functions(tree: exp.Expression) -> None:
    for func in tree.find_all(exp.Func):
        name = (func.name or type(func).__name__).lower()
        if (
            name in FORBIDDEN_FUNCTIONS
            or name.startswith(FORBIDDEN_FUNCTION_PREFIXES)
            or type(func).__name__.lower().startswith(("read", "write"))
        ):
            raise SQLValidationError(f"Function '{name}' is not allowed.")


def _check_columns(tree: exp.Expression, columns: list[str]) -> None:
    known = {c.lower() for c in columns}
    # Names the query itself creates (SELECT x AS total, CTE names) are valid too.
    known |= {a.alias.lower() for a in tree.find_all(exp.Alias) if a.alias}
    known |= {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for col in tree.find_all(exp.Column):
        if col.name.lower() not in known:
            raise SQLValidationError(f"Unknown column '{col.name}'.")
