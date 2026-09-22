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

    The current DataFrame is table ``data`` (same as CLI ``-sql``). Extra keyword
    frames are registered under those names, like ``-file`` aliases.

    Parameters
    ----------
    df:
        Registered as table ``data``.
    query:
        DuckDB SQL. Spaced column names need double quotes.
    **frames:
        Additional DataFrames registered as tables. The name ``data`` is reserved.

    Examples
    --------
    >>> import pytae as pt
    >>> penguins = pt.sample("penguins")
    >>> pt.sql(penguins, "select species, avg(body_mass_g) as avg_mass from data group by species order by species")
         species     avg_mass
    0     Adelie  3700.662252
    1  Chinstrap  3733.088235
    2     Gentoo  5076.016260
    >>> penguins.pt.sql("select * from data where species = 'Adelie'").shape
    (152, 7)
    >>> left = pd.DataFrame({"id": [1, 2], "x": ["a", "b"]})
    >>> right = pd.DataFrame({"id": [1, 3], "y": ["p", "q"]})
    >>> pt.sql(left, "select data.id, x, y from data join extra using (id)", extra=right)
       id  x  y
    0   1  a  p
    """
    if "data" in frames:
        raise ValueError("sql(): extra frame cannot be named 'data' — that's the current DataFrame")
    tables = {"data": df, **frames}
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
