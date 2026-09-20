"""SQL over DataFrames via duckdb. Optional extra: pip install 'pytae[sql]'."""

from __future__ import annotations

import pandas as pd


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise ImportError(
            "sql() requires duckdb. Install with: pip install 'pytae[sql]'"
        ) from exc
    return duckdb


def sql(df: pd.DataFrame, query: str, /, **frames: pd.DataFrame) -> pd.DataFrame:
    """Run a SQL query via duckdb.

    The current DataFrame is table ``df`` (same as CLI ``-sql``). Extra keyword
    frames are registered under those names, like ``-file`` aliases.

    Parameters
    ----------
    df:
        Registered as table ``df``.
    query:
        DuckDB SQL. Spaced column names need double quotes.
    **frames:
        Additional DataFrames registered as tables. The name ``df`` is reserved.

    Examples
    --------
    >>> import pytae as pt
    >>> penguins = pt.sample("penguins")
    >>> pt.sql(penguins, "select species, avg(body_mass_g) as avg_mass from df group by species")
    >>> penguins.pt.sql("select * from df where species = 'Adelie'")
    >>> pt.sql(left, "select * from df join extra using (id)", extra=right)
    """
    if "df" in frames:
        raise ValueError("sql(): extra frame cannot be named 'df' — that's the current DataFrame")
    tables = {"df": df, **frames}
    duckdb = _require_duckdb()
    con = duckdb.connect()
    try:
        for name, frame in tables.items():
            con.register(name, frame)
        try:
            return con.sql(query).df()
        except Exception as exc:
            raise ValueError(f"sql: {exc}") from exc
    finally:
        con.close()
