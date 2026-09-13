"""The _Pipeline view and the argparse Actions that record CLI flag order (op_order)."""

from __future__ import annotations

import argparse
import re

import pandas as pd

from pytae.cli_parsing import _select_unknown_names, unknown_columns_message


class _Pipeline:
    """Flag order is the method chain. Each -select/-qry/-query/-head/… call
    runs on the current view, same as df.select().qry().head().
    Only the last flag prints. Schema-only ops (-cols/-dtype/-shape) avoid loading
    row data until something actually requires it. -shape/-cols/-dtype/-nulls/-info
    don't return a DataFrame/Series in pandas either, so (like main()'s validation)
    nothing may follow them except -to_clip.
    """

    def __init__(self, reader=None, *, nrows=None, progress=False) -> None:
        self._reader = reader
        self._nrows = nrows
        self._progress = progress
        self._df: pd.DataFrame | None = None
        self._pending_exact: list[str] | None = None

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
            self._df = df.select(*names, **kwargs)
        except (ValueError, KeyError) as exc:
            return f"-select: {exc}"
        return None

    def apply_qry(self, conditions: dict) -> str | None:
        """Apply one -qry spec to the current view. Returns an error message or None."""
        df = self.dataframe()
        try:
            self._df = df.qry(conditions)
        except Exception as exc:
            return f"-qry: {exc}"
        return None

    def apply_query(self, expr: str) -> str | None:
        """Apply one -query expression to the current view. Returns an error message or None."""
        df = self.dataframe()
        try:
            self._df = df.query(expr)
        except Exception as exc:
            return f"-query: {exc}"
        return None

    def apply_replace(self, cols: list[str] | None, mapping: dict[str, str], exact: bool) -> str | None:
        """Apply one -replace spec to the current view. Returns an error message or None."""
        df = self.dataframe()
        if cols is not None:
            available = list(df.columns)
            unknown = [c for c in cols if c not in available]
            if unknown:
                return unknown_columns_message("-replace", unknown, available)
            target = df[cols]
        else:
            target = df
        to_replace = mapping if exact else {re.escape(k): v for k, v in mapping.items()}
        try:
            replaced = target.replace(to_replace, regex=not exact)
        except Exception as exc:
            return f"-replace: {exc}"
        if cols is not None:
            df = df.copy()
            df[cols] = replaced
            self._df = df
        else:
            self._df = replaced
        return None

    def apply_sql(self, query: str) -> str | None:
        """Apply one -sql query to the current view via duckdb. The view is registered as
        table `df` (the file itself is already named on the command line, so there's no
        separate file-derived alias). Returns an error message or None."""
        try:
            import duckdb
        except ImportError as exc:
            return f"-sql requires duckdb. Install with: pip install 'pytae[sql]' ({exc})"
        con = duckdb.connect()
        try:
            con.register("df", self.dataframe())
            try:
                self._df = con.sql(query).df()
            except Exception as exc:
                return f"-sql: {exc}"
        finally:
            con.close()
        return None

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
            df = self._reader.head(n)
            if self._pending_exact is not None:
                df = df.select(*self._pending_exact)
        else:
            df = self.dataframe().head(n)
        self._df = df
        return df

    def tail(self, n: int) -> pd.DataFrame:
        if self._df is None:
            df = self._reader.tail(n)
            if self._pending_exact is not None:
                df = df.select(*self._pending_exact)
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


class _OrderedSortBy(argparse.Action):
    """-sort_by COLUMNS [asc|desc]; records dest in op_order. Default direction is asc."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        values = list(values)
        order = "asc"
        if len(values) >= 2 and values[-1] in ("asc", "desc"):
            order = values.pop()
        if len(values) != 1:
            raise argparse.ArgumentError(
                self, "expected a column list, optionally followed by 'asc' or 'desc'"
            )
        setattr(namespace, self.dest, values[0])
        setattr(namespace, "sort_by_order", order)
        namespace.op_order = getattr(namespace, "op_order", []) + [self.dest]
