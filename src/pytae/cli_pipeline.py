"""The _Pipeline view and the argparse Actions that record CLI flag order (op_order)."""

from __future__ import annotations

import argparse
import re

import pandas as pd

from pytae.cli_parsing import _select_unknown_names, unknown_columns_message
from pytae.mutate import mutate
from pytae.other_utilities import replace_values
from pytae.qry import qry
from pytae.select import select


def _sql_string_literal(value: str) -> str:
    """Quote a plain Python string as a SQL string literal (escaping embedded quotes) —
    duckdb table functions like read_parquet()/read_csv() can't be parameterized via
    prepared-statement placeholders, so the path/delimiter must be inlined as a literal."""
    return "'" + value.replace("'", "''") + "'"


def _mask_quoted(spec: str) -> str:
    """Blank out the contents of quoted substrings in spec (keeping overall length/
    positions), so a regex check on the result only ever sees text outside string
    literals -- e.g. an '@' inside a quoted value like 'a@b' is masked out."""
    out = []
    quote: str | None = None
    for ch in spec:
        if quote:
            out.append(ch if ch == quote else " ")
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
        out.append(ch)
    return "".join(out)


class _Pipeline:
    """Flag order is the method chain. Each -select/-drop/-qry/-query/-head/… call
    runs on the current view, same as pt.select(df, …) then pt.qry(df, …) then head.
    Only the last flag prints. Schema-only ops (-cols/-dtype/-shape) avoid loading
    row data until something actually requires it. -shape/-cols/-dtype/-nulls/-info
    don't return a DataFrame/Series in pandas either, so (like main()'s validation)
    nothing may follow them except -to_clip.
    """

    def __init__(self, reader=None, *, nrows=None, progress=False, frames=None) -> None:
        self._reader = reader
        self._nrows = nrows
        self._progress = progress
        self._df: pd.DataFrame | None = None
        self._pending_exact: list[str] | None = None
        self._frames: dict[str, pd.DataFrame] = frames or {}

    def _available_columns(self) -> list[str]:
        if self._df is not None:
            return list(self._df.columns)
        if self._pending_exact is not None:
            return list(self._pending_exact)
        return list(self._reader.columns())

    def apply_select(self, names: list[str], kwargs: dict) -> str | None:
        """Apply one -select spec to the current view. Returns an error message or None."""
        available = self._available_columns()
        unknown = _select_unknown_names(names, available)
        if unknown:
            return unknown_columns_message("-select", unknown, available)

        needs_frame = (
            self._df is not None
            or bool(kwargs)
            or any(":" in token for token in names)
        )
        if not needs_frame:
            self._pending_exact = list(names)
            return None

        df = self._df if self._df is not None else self.dataframe()
        try:
            self._df = select(df, *names, **kwargs)
        except (ValueError, KeyError) as exc:
            return f"-select: {exc}"
        return None

    def apply_drop(self, names: list[str]) -> str | None:
        """Apply one -drop spec (exact column names) to the current view.

        Remaining columns keep their existing order. Returns an error message or None.
        """
        available = self._available_columns()
        unknown = [c for c in names if c not in available]
        if unknown:
            msg = unknown_columns_message("-drop", unknown, available)
            if any(":" in c for c in unknown):
                msg += " (-drop does not accept slices; use -select)"
            return msg
        drop_set = set(names)
        remaining = [c for c in available if c not in drop_set]
        if not remaining:
            return "-drop: no columns left"
        if self._df is not None:
            self._df = self._df.drop(columns=list(dict.fromkeys(names)))
        else:
            self._pending_exact = remaining
        return None

    def apply_qry(self, conditions: dict) -> str | None:
        """Apply one -qry spec to the current view. Returns an error message or None."""
        df = self.dataframe()
        try:
            self._df = qry(df, **conditions)
        except Exception as exc:
            return f"-qry: {exc}"
        return None

    def apply_mutate(self, spec: str) -> str | None:
        """Apply one -mutate spec to the current view. Returns an error message or None."""
        raw_spec = spec.strip()
        if raw_spec.startswith("@"):
            path = raw_spec[1:].strip()
            from pathlib import Path
            file_path = Path(path)
            if not file_path.is_file():
                return f"-mutate: spec file not found: '{path}'"
            try:
                raw_spec = file_path.read_text(encoding="utf-8").strip()
            except Exception as exc:
                return f"-mutate: failed to read spec file '{path}': {exc}"
        if re.search(r"@\w", _mask_quoted(raw_spec)):
            return "-mutate: '@name' local-variable references are library-only (pt.mutate() from Python), not available on the CLI"
        df = self.dataframe()
        try:
            from pytae.mutate import parse_mutate_spec
            parsed = parse_mutate_spec(raw_spec)
            self._df = mutate(df, **parsed)
        except Exception as exc:
            return f"-mutate: {exc}"
        return None

    def apply_query(self, expr: str) -> str | None:
        """Apply one -query expression to the current view. Returns an error message or None."""
        df = self.dataframe()
        try:
            self._df = df.query(expr)
        except Exception as exc:
            return f"-query: {exc}"
        return None

    def apply_replace_values(self, cols: list[str] | None, mapping: dict[str, str], exact: bool) -> str | None:
        """Apply one -replace_values spec to the current view. Returns an error message or None."""
        df = self.dataframe()
        if cols is not None:
            available = list(df.columns)
            unknown = [c for c in cols if c not in available]
            if unknown:
                return unknown_columns_message("-replace_values", unknown, available)
        try:
            self._df = replace_values(df, v=mapping, c=cols, exact=exact)
        except Exception as exc:
            return f"-replace_values: {exc}"
        return None

    def apply_sql(self, query: str) -> str | None:
        """Apply one -sql query via duckdb. Single-file mode: the current view is registered
        as table `data` (the file itself is already named on the command line, so there's no
        separate file-derived alias) — if nothing has touched the view yet, duckdb scans the
        source parquet/csv/txt/dat file directly instead of first materializing it through
        pandas (much faster; pandas is only used as a fallback, see _register_source_view).
        -file/-merge mode: every -file alias is registered under its own name instead, so
        -sql can do the join itself; `data` is also registered once something (e.g. -merge)
        has produced a current view. Returns an error message or None."""
        try:
            import duckdb
        except ImportError as exc:
            return f"-sql requires duckdb. Install with: pip install 'pytae[sql]' ({exc})"
        q = query.strip()
        if q.startswith("@"):
            path = q[1:].strip()
            from pathlib import Path
            file_path = Path(path)
            if not file_path.is_file():
                return f"-sql: query file not found: '{path}'"
            try:
                q = file_path.read_text(encoding="utf-8").strip()
            except Exception as exc:
                return f"-sql: failed to read query file '{path}': {exc}"
        from pytae.sql import _normalize_sql
        normalized_query = _normalize_sql(q)
        con = duckdb.connect()
        try:
            for alias, frame in self._frames.items():
                con.register(alias, frame)
            if self._df is not None:
                con.register("data", self._df)
            elif self._reader is not None:
                if not self._register_source_view(con):
                    con.register("data", self.dataframe())
            try:
                self._df = con.sql(normalized_query).df()
            except Exception as exc:
                return f"-sql: {exc}"
        finally:
            con.close()
        return None

    def _register_source_view(self, con) -> bool:
        """Best-effort: have duckdb scan the source file directly and register the
        result as view `df`, instead of first materializing it through pandas
        (self.dataframe()). Returns False when the fast path doesn't apply (a prior
        op already narrowed columns, -progress was requested, or the source format
        has no fast native duckdb reader e.g. .sas7bdat) — the caller then falls
        back to the pandas-backed view."""
        from pytae.readers import CsvReader, ParquetReader, TxtReader

        if self._pending_exact is not None or self._progress:
            return False
        reader = self._reader
        path_sql = _sql_string_literal(str(reader.path))
        if isinstance(reader, ParquetReader):
            scan = f"read_parquet({path_sql})"
        elif isinstance(reader, (CsvReader, TxtReader)):
            if reader.encoding not in (None, "utf-8", "utf8"):
                return False  # duckdb's CSV reader doesn't support arbitrary encodings
            scan = f"read_csv({path_sql}, delim={_sql_string_literal(reader.sep)}, header=true)"
        else:
            return False  # e.g. .sas7bdat -- duckdb has no native reader for it
        limit_sql = f" LIMIT {int(self._nrows)}" if self._nrows is not None else ""
        con.execute(f"CREATE VIEW data AS SELECT * FROM {scan}{limit_sql}")
        return True

    def dataframe(self) -> pd.DataFrame:
        if self._df is None:
            df = self._reader.to_dataframe(
                columns=self._pending_exact, nrows=self._nrows, progress=self._progress,
            )
            self._df = df
        return self._df

    def columns(self) -> list[str]:
        if self._df is not None:
            return list(self._df.columns)
        return self._available_columns()

    def dtypes(self) -> pd.Series:
        if self._df is not None:
            return self._df.dtypes
        dtypes = self._reader.dtypes()
        return dtypes[self._pending_exact] if self._pending_exact is not None else dtypes

    def shape(self) -> tuple[int, int]:
        if self._df is not None:
            return self._df.shape
        rows = self._reader.shape()[0]
        cols = len(self._pending_exact) if self._pending_exact is not None else self._reader.shape()[1]
        return (rows, cols)

    def head(self, n: int) -> pd.DataFrame:
        if self._df is None:
            if self._nrows is not None:
                df = self.dataframe().head(n)
            else:
                df = self._reader.head(n)
                if self._pending_exact is not None:
                    df = select(df, *self._pending_exact)
        else:
            df = self.dataframe().head(n)
        self._df = df
        return df

    def tail(self, n: int) -> pd.DataFrame:
        if self._df is None:
            if self._nrows is not None:
                df = self.dataframe().tail(n)
            else:
                df = self._reader.tail(n)
                if self._pending_exact is not None:
                    df = select(df, *self._pending_exact)
        else:
            df = self.dataframe().tail(n)
        self._df = df
        return df

    def sample(self, n: int, *, seed: int | None = None, frac: float | None = None) -> pd.DataFrame:
        df = self.dataframe()
        if frac is not None:
            sampled = df.sample(frac=frac, random_state=seed)
        else:
            n = min(n, len(df))
            sampled = df.sample(n=n, random_state=seed) if n else df.iloc[0:0]
        self._df = sampled
        return sampled


class _OrderedFlag(argparse.Action):
    """Boolean flag (like store_true) that also records its dest in namespace.op_order, in CLI order."""

    def __init__(self, option_strings, dest, **kwargs) -> None:
        super().__init__(option_strings, dest, nargs=0, default=False, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, True)
        namespace.op_order = getattr(namespace, "op_order", []) + [self.dest]


class _OrderedValue(argparse.Action):
    """Optional-value flag (nargs='?') that also records its dest in namespace.op_order, in CLI order."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, self.const if values is None else values)
        namespace.op_order = getattr(namespace, "op_order", []) + [self.dest]


class _OrderedStore(argparse.Action):
    """Required-value flag (nargs=default) that also records its dest in namespace.op_order, in CLI order."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, values)
        namespace.op_order = getattr(namespace, "op_order", []) + [self.dest]


class _OrderedAppend(argparse.Action):
    """Collect repeated flags into a list and record each occurrence in op_order."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        items = getattr(namespace, self.dest, None)
        items = [] if items is None else list(items)
        items.append(values)
        setattr(namespace, self.dest, items)
        namespace.op_order = getattr(namespace, "op_order", []) + [self.dest]
