"""The _Pipeline view and the argparse Actions that record CLI flag order (op_order)."""

from __future__ import annotations

import argparse
import re
from typing import Any

import pandas as pd

from pytae._text import unquote_name as _unquote_name
from pytae.cli_parsing import _select_unknown_names, unknown_columns_message


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
    """Flag order is the method chain. Each -select/-qry/-query/-head/… call
    runs on the current view, same as pt.select(df, …) then pt.qry(df, …) then head.
    Only the last flag prints. Schema-only ops (-cols/-dtype/-shape) avoid loading
    row data until something actually requires it. -shape/-cols/-dtype/-nulls/-info
    don't return a DataFrame/Series in pandas either, so (like main()'s validation)
    nothing may follow them except -o clip.
    """

    def __init__(self, reader=None, *, nrows=None, progress=False, frames=None, chunk_size: int = 200_000) -> None:
        self._reader = reader
        self._nrows = nrows
        self._progress = progress
        self._chunk_size = chunk_size
        self._pandas_df: pd.DataFrame | None = None
        self._pldf: Any | None = None
        self._pending_exact: list[str] | None = None
        self._frames: dict[str, Any] = frames or {}

    @property
    def _df(self) -> pd.DataFrame | None:
        return self._pandas_df

    @_df.setter
    def _df(self, value: pd.DataFrame | None) -> None:
        self._pandas_df = value
        if value is not None:
            self._pldf = None

    def _available_columns(self) -> list[str]:
        if self._pldf is not None:
            if hasattr(self._pldf, "collect_schema"):
                return list(self._pldf.collect_schema().names())
            return list(self._pldf.columns)
        if self._df is not None:
            return list(self._df.columns)
        if self._pending_exact is not None:
            return list(self._pending_exact)
        return list(self._reader.columns())

    def polars_lazy_frame(self):
        """Get the current view as a LazyFrame (or converted to lazy if already eager)."""
        import polars as pl

        if self._pldf is None:
            if self._df is not None:
                self._pldf = pl.from_pandas(self._df).lazy()
            elif self._reader is not None:
                try:
                    if hasattr(self._reader, "to_polars_lazy") and not self._progress and self._nrows is None:
                        self._pldf = self._reader.to_polars_lazy(columns=self._pending_exact)
                    else:
                        eager = self._reader.to_polars(columns=self._pending_exact, nrows=self._nrows)
                        self._pldf = eager.lazy() if isinstance(eager, pl.DataFrame) else eager
                    self._pending_exact = None
                except Exception:
                    df = self.dataframe()
                    self._pldf = pl.from_pandas(df).lazy()
            else:
                self._pldf = pl.LazyFrame()
        elif isinstance(self._pldf, pl.DataFrame):
            self._pldf = self._pldf.lazy()
        return self._pldf

    def polars_frame(self):
        """Get the active frame collected into an eager Polars DataFrame."""
        import polars as pl

        lf = self.polars_lazy_frame()
        if isinstance(lf, pl.LazyFrame):
            self._pldf = lf.collect()
        return self._pldf

    def apply_select(self, names: list[str], kwargs: dict) -> str | None:
        """Apply one -select spec to the current view. Returns an error message or None."""
        available = self._available_columns()
        unknown = _select_unknown_names(names, available)
        if unknown:
            return unknown_columns_message("-select", unknown, available)

        needs_frame = (
            self._pldf is not None
            or self._df is not None
            or bool(kwargs)
            or any(":" in token for token in names)
            or any(token.startswith(("-", "~")) for token in names)
        )
        if not needs_frame:
            self._pending_exact = [_unquote_name(n) for n in names]
            return None

        try:
            from pytae.polars_engine import select_polars

            self._pldf = select_polars(self.polars_lazy_frame(), names, kwargs)
            self._df = None
            return None
        except Exception as exc:
            return f"-select: {exc}"

    def apply_rename(self, mapping: dict[str, str]) -> str | None:
        """Apply one -rename mapping to the current view. Returns an error message or None."""
        available = self._available_columns()
        unknown = [c for c in mapping if c not in available]
        if unknown:
            return unknown_columns_message("-rename", unknown, available)
        try:
            from pytae.polars_engine import rename_polars

            self._pldf = rename_polars(self.polars_lazy_frame(), mapping)
            self._df = None
            return None
        except Exception as exc:
            return f"-rename: {exc}"

    def apply_filter(self, conditions: list[tuple[str, Any]] | dict, flag_name: str = "-filter") -> str | None:
        """Apply one -filter (or -qry) spec to the current view. Returns an error message or None."""
        available = self._available_columns()
        cond_cols = [c for c, _ in (conditions if isinstance(conditions, list) else conditions.items())]
        unknown = [c for c in cond_cols if c not in available]
        if unknown:
            return unknown_columns_message(flag_name, unknown, available)

        try:
            from pytae.polars_engine import filter_polars

            self._pldf = filter_polars(self.polars_lazy_frame(), conditions)
            self._df = None
            return None
        except Exception as exc:
            return f"{flag_name}: {exc}"

    def apply_mutate(self, spec: str, by: list[str] | None = None, dropna: bool = False) -> str | None:
        """Apply one -mutate spec to the current view. Returns an error message or None."""
        raw_spec = spec.strip()
        if (raw_spec.startswith("'") and raw_spec.endswith("'")) or (
            raw_spec.startswith('"') and raw_spec.endswith('"')
        ):
            raw_spec = raw_spec[1:-1].strip()
        if raw_spec.startswith("@"):
            path = raw_spec[1:].strip()
            if (path.startswith("'") and path.endswith("'")) or (path.startswith('"') and path.endswith('"')):
                path = path[1:-1].strip()
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
        from pytae._parsing import parse_mutate_spec

        try:
            parsed = parse_mutate_spec(raw_spec)
        except Exception as exc:
            return f"-mutate: {exc}"

        try:
            from pytae.polars_engine import mutate_polars

            self._pldf = mutate_polars(self.polars_lazy_frame(), parsed, by=by, dropna=dropna)
            self._df = None
            return None
        except Exception as exc:
            return f"-mutate: {exc}"

    def apply_cast(self, spec: str) -> str | None:
        """Cast column types using Polars native SIMD vectorization. Returns an error message or None."""
        try:
            from pytae.polars_engine import cast_polars

            self._pldf = cast_polars(self.polars_lazy_frame(), dtypes=spec)
            self._df = None
            return None
        except Exception as exc:
            return f"-cast: {exc}"

    def apply_dropna(self, spec: str | None) -> str | None:
        """Drop rows containing missing values (null/NaN). Returns an error message or None."""
        from pytae.cli_parsing import parse_dropna_spec, unknown_columns_message

        available = self._available_columns()
        try:
            cols, how, drop_nans = parse_dropna_spec(spec, flag_name="-dropna", available_cols=available)
        except SystemExit as exc:
            return str(exc)

        if cols:
            unknown = [c for c in cols if c not in available]
            if unknown:
                return unknown_columns_message("-dropna", unknown, available)

        try:
            from pytae.polars_engine import dropna_polars

            self._pldf = dropna_polars(
                self.polars_lazy_frame(),
                cols=cols if cols else None,
                how=how,
                drop_nans=drop_nans,
            )
            self._df = None
            return None
        except Exception as exc:
            return f"-dropna: {exc}"

    def apply_distinct(self, spec: str | None) -> str | None:
        """Drop duplicate rows. Returns an error message or None."""
        from pytae.cli_parsing import parse_distinct_spec, unknown_columns_message

        try:
            cols, keep = parse_distinct_spec(spec)
        except SystemExit as exc:
            return str(exc)
        available = self._available_columns()
        if cols:
            unknown = [c for c in cols if c not in available]
            if unknown:
                return unknown_columns_message("-distinct", unknown, available)
        try:
            from pytae.polars_engine import distinct_polars

            self._pldf = distinct_polars(self.polars_lazy_frame(), cols=cols, keep=keep)
            self._df = None
            return None
        except Exception as exc:
            return f"-distinct: {exc}"

    def apply_arrange(self, spec: str) -> str | None:
        """Sort rows by one or more columns with directions. Returns an error message or None."""
        try:
            from pytae.polars_engine import arrange_polars

            self._pldf = arrange_polars(self.polars_lazy_frame(), spec)
            self._df = None
            return None
        except Exception as exc:
            return f"-arrange: {exc}"

    def apply_pick(self, spec: str, *, by: list[str] | None = None, flag: str = "-pick") -> str | None:
        """Pick top or bottom rows by a column, optionally grouped by 'by'."""
        from pytae.cli_parsing import parse_pick_spec, unknown_columns_message

        try:
            col, n, prop, order = parse_pick_spec(spec, flag)
        except SystemExit as exc:
            return str(exc)
        available = self._available_columns()
        clean_col = _unquote_name(col.strip())
        if clean_col not in available:
            return unknown_columns_message(flag, [clean_col], available)
        if by:
            unknown_by = [c for c in by if c not in available]
            if unknown_by:
                return unknown_columns_message("-by", unknown_by, available)
        try:
            from pytae.polars_engine import pick_polars

            self._pldf = pick_polars(self.polars_lazy_frame(), clean_col, n=n, prop=prop, order=order, by=by)
            self._df = None
            return None
        except Exception as exc:
            return f"{flag}: {exc}"

    def apply_replace_values(self, cols: list[str] | None, mapping: dict[str, str], exact: bool) -> str | None:
        """Apply one -replace_values spec to the current view. Returns an error message or None."""
        available = self._available_columns()
        if cols is not None:
            unknown = [c for c in cols if c not in available]
            if unknown:
                return unknown_columns_message("-replace_values", unknown, available)
        try:
            from pytae.polars_engine import replace_values_polars

            self._pldf = replace_values_polars(self.polars_lazy_frame(), v=mapping, c=cols, exact=exact)
            self._df = None
            return None
        except Exception as exc:
            return f"-replace_values: {exc}"
        return None

    def apply_sql(self, query: str) -> str | None:
        """Apply one -sql query via Polars SQLContext. Single-file mode: the current view is registered
        as table `data` (the file itself is already named on the command line, so there's no
        separate file-derived alias).
        -file/-join mode: every -file alias is registered under its own name instead, so
        -sql can do the join itself; `data` is also registered once something (e.g. -join)
        has produced a current view. Returns an error message or None."""
        import re

        import polars as pl

        from pytae.cli_parsing import normalize_sql

        try:
            normalized_query = normalize_sql(query)
        except Exception as exc:
            return f"-sql: {exc}"
        polars_query = re.sub(r"\bin\s*\[(.*?)\]", r"in (\1)", normalized_query, flags=re.IGNORECASE)

        try:
            if self._progress and self._reader is not None:
                self.dataframe()
            tables: dict[str, pl.DataFrame] = {}
            for alias, frame in self._frames.items():
                tables[alias] = pl.from_pandas(frame) if isinstance(frame, pd.DataFrame) else frame
            tables["data"] = self.polars_frame()
            ctx = pl.SQLContext(frames=tables)
            res_pl = ctx.execute(polars_query).collect()
            self._pldf = res_pl
            self._df = None
            return None
        except Exception as polars_err:
            return f"-sql: {polars_err}"

    def dataframe(self) -> pd.DataFrame:
        if self._pandas_df is None:
            if self._pldf is not None:
                pldf = self.polars_frame()
                self._pandas_df = pldf.to_pandas()
            else:
                df = self._reader.to_dataframe(
                    columns=self._pending_exact,
                    nrows=self._nrows,
                    progress=self._progress,
                    chunk_size=self._chunk_size,
                )
                self._pandas_df = df
        return self._pandas_df

    def columns(self) -> list[str]:
        if self._pldf is not None:
            if hasattr(self._pldf, "collect_schema"):
                return list(self._pldf.collect_schema().names())
            return list(self._pldf.columns)
        if self._df is not None:
            return list(self._df.columns)
        return self._available_columns()

    def dtypes(self) -> pd.Series:
        if self._pldf is not None:
            if hasattr(self._pldf, "collect"):
                return self._pldf.head(0).collect().to_pandas().dtypes
            return self._pldf.head(0).to_pandas().dtypes
        if self._df is not None:
            return self._df.dtypes
        dtypes = self._reader.dtypes()
        return dtypes[self._pending_exact] if self._pending_exact is not None else dtypes

    def shape(self) -> tuple[int, int]:
        if self._pldf is not None:
            if hasattr(self._pldf, "collect"):
                import polars as pl

                return (
                    self._pldf.select(pl.len()).collect().item(),
                    len(self._pldf.collect_schema().names()),
                )
            return self._pldf.shape
        if self._df is not None:
            return self._df.shape
        rows = self._reader.shape()[0]
        cols = len(self._pending_exact) if self._pending_exact is not None else self._reader.shape()[1]
        return (rows, cols)

    def current_frame(self) -> Any:
        """Return the active frame (preferring Polars to avoid needless Pandas conversions)."""
        if self._progress:
            return self.dataframe()
        if self._df is not None:
            return self._df
        return self.polars_frame()

    def head(self, n: int) -> Any:
        if self._progress:
            df = self.dataframe().head(n)
            self._df = df
            self._pldf = None
            return df
        lf = self.polars_lazy_frame()
        self._pldf = lf.head(n).collect()
        self._df = None
        return self._pldf

    def tail(self, n: int) -> Any:
        if self._progress:
            df = self.dataframe().tail(n)
            self._df = df
            self._pldf = None
            return df
        lf = self.polars_lazy_frame()
        self._pldf = lf.tail(n).collect()
        self._df = None
        return self._pldf

    def sample(self, n: int, *, seed: int | None = None, frac: float | None = None) -> Any:
        if self._progress:
            df = self.dataframe()
            if not (isinstance(df.index, pd.RangeIndex) and df.index.name is None):
                df = df.reset_index()
            if frac is not None:
                sampled = df.sample(frac=frac, random_state=seed)
            else:
                n = min(n, len(df))
                sampled = df.sample(n=n, random_state=seed) if n else df.iloc[0:0]
            sampled = sampled.reset_index(drop=True)
            self._df = sampled
            self._pldf = None
            return sampled

        pldf = self.polars_frame()
        if frac is not None:
            sampled_pl = pldf.sample(fraction=frac, seed=seed)
        else:
            n_rows = len(pldf)
            sample_n = min(n, n_rows)
            sampled_pl = pldf.sample(n=sample_n, seed=seed) if sample_n > 0 else pldf.head(0)
        self._pldf = sampled_pl
        self._df = None
        return sampled_pl


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
        val = self.const if values is None else values
        setattr(namespace, self.dest, val)
        flag_name = option_string.lstrip("-") if option_string else self.dest
        namespace.op_order = getattr(namespace, "op_order", []) + [flag_name]
        op_values = getattr(namespace, "_op_values", None)
        if op_values is None:
            op_values = {}
            setattr(namespace, "_op_values", op_values)
        op_values.setdefault(flag_name, []).append(val)
        if flag_name != self.dest:
            op_values.setdefault(self.dest, []).append(val)


class _OrderedStore(argparse.Action):
    """Required-value flag (nargs=default) that also records its dest in namespace.op_order, in CLI order."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, values)
        flag_name = option_string.lstrip("-") if option_string else self.dest
        namespace.op_order = getattr(namespace, "op_order", []) + [flag_name]
        op_values = getattr(namespace, "_op_values", None)
        if op_values is None:
            op_values = {}
            setattr(namespace, "_op_values", op_values)
        op_values.setdefault(flag_name, []).append(values)
        if flag_name != self.dest:
            op_values.setdefault(self.dest, []).append(values)


class _OrderedAppend(argparse.Action):
    """Collect repeated flags into a list and record each occurrence in op_order."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        items = getattr(namespace, self.dest, None)
        items = [] if items is None else list(items)
        items.append(values)
        setattr(namespace, self.dest, items)
        flag_name = option_string.lstrip("-") if option_string else self.dest
        namespace.op_order = getattr(namespace, "op_order", []) + [flag_name]
