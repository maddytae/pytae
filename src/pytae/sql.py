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


def _normalize_sql(query: str) -> str:
    """Normalize query: read from @path if given, and convert [col] and `col` to \"col\"."""
    q = query.strip()
    if q.startswith("@"):
        path = q[1:].strip()
        from pathlib import Path
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"sql: query file not found: '{path}'")
        q = file_path.read_text(encoding="utf-8").strip()
    out_chars: list[str] = []
    i, n = 0, len(q)
    quote = None
    while i < n:
        ch = q[i]
        if quote is not None:
            out_chars.append(ch)
            if ch == quote:
                if i + 1 < n and q[i + 1] == quote:
                    out_chars.append(q[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out_chars.append(ch)
            i += 1
            continue
        if ch == "`":
            j = q.find("`", i + 1)
            if j != -1:
                ident = q[i + 1 : j]
                out_chars.append(f'"{ident}"')
                i = j + 1
                continue
        if ch == "[":
            j = q.find("]", i + 1)
            if j != -1:
                inner = q[i + 1 : j]
                if any(c.isalpha() or c in " _-" for c in inner):
                    out_chars.append(f'"{inner}"')
                    i = j + 1
                    continue
        out_chars.append(ch)
        i += 1
    return "".join(out_chars)


def sql(df: pd.DataFrame, query: str, /, **frames: pd.DataFrame) -> pd.DataFrame:
    """Run a SQL query via duckdb.

    The current DataFrame is table ``data`` (same as CLI ``-sql``). Extra keyword
    frames are registered under those names, like ``-file`` aliases.

    Parameters
    ----------
    df:
        Registered as table ``data``.
    query:
        DuckDB SQL, or '@query.txt' to load from a file. Spaced column names can
        use double quotes (\"col a\"), brackets ([col a]), or backticks (`col a`).
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
    normalized_query = _normalize_sql(query)
    tables = {"data": df, **frames}
    duckdb = _require_duckdb()
    con = duckdb.connect()
    try:
        for name, frame in tables.items():
            con.register(name, frame)
        try:
            return con.sql(normalized_query).df()
        except Exception as exc:
            raise ValueError(f"sql: {exc}") from exc
    finally:
        con.close()

