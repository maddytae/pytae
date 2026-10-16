"""Pytae DataFrame: A first-class tabular data frame powered natively by Polars."""

from __future__ import annotations

import platform
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import polars as pl

from pytae._parsing import _parse_filter_string, _parse_mutate_spec_entries
from pytae._text import unquote_name as _unquote_name
from pytae.polars_engine import (
    agg_polars,
    arrange_polars,
    cast_polars,
    clean_columns_polars,
    concat_polars,
    distinct_polars,
    dropna_polars,
    fill_nan_polars,
    fillna_polars,
    filter_polars,
    handle_missing_polars,
    join_polars,
    long_polars,
    mutate_polars,
    pick_polars,
    pivot_polars,
    replace_values_polars,
    select_polars,
    wide_polars,
)


def _copy_to_clipboard(text: str) -> None:
    """Copy text to the system clipboard via pbcopy/clip/xclip."""
    system = platform.system()
    if system == "Darwin":
        cmd = ["pbcopy"]
    elif system == "Windows":
        cmd = ["clip"]
    else:
        cmd = ["xclip", "-selection", "clipboard"]
    try:
        subprocess.run(cmd, input=text.encode("utf-8"), check=True)
    except Exception:
        pass


class ColumnNames(list[str]):
    """A list of column names with helper compatibility attributes like .name and .tolist()."""

    @property
    def name(self) -> None:
        return None

    def tolist(self) -> list[str]:
        return list(self)

    def to_list(self) -> list[str]:
        return list(self)

    def get_indexer_for(self, target: Any) -> Any:
        try:
            import pandas as pd

            return pd.Index(self).get_indexer_for(target)
        except Exception:
            return [self.index(x) if x in self else -1 for x in target]

    def _get_level_values(self, i: int) -> Any:
        import pandas as pd

        return pd.Index(self)


class _IlocIndexer:
    """Row/column indexer for compatibility with Pandas iloc syntax."""

    def __init__(self, df: DataFrame):
        self._df = df

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, int):
            row_dict = self._df._df.row(item, named=True)
            import pandas as pd

            return pd.Series(row_dict)
        elif isinstance(item, tuple) and len(item) == 2:
            row_idx, col_idx = item
            if isinstance(col_idx, int):
                col_name = self._df._df.columns[col_idx]
                return self._df._df[row_idx, col_name]
            elif isinstance(col_idx, str):
                return self._df._df[row_idx, col_idx]
        return self._df._df[item]

    def __setitem__(self, item: Any, value: Any) -> None:
        if isinstance(item, tuple) and len(item) == 2:
            row_idx, col_idx = item
            if isinstance(col_idx, int):
                col_name = self._df._df.columns[col_idx]
            else:
                col_name = str(col_idx)
            s_list = self._df._df[col_name].to_list()
            s_list[row_idx] = value
            self._df._df = self._df._df.with_columns(pl.Series(col_name, s_list))


class _LocIndexer:
    """Row/column label-based indexer for compatibility with Pandas loc syntax."""

    def __init__(self, df: DataFrame):
        self._df = df

    def __getitem__(self, item: Any) -> Any:
        import polars as pl

        if isinstance(item, tuple):
            rows = item[0]
            if isinstance(rows, pl.Series):
                rows = rows.to_pandas()
            item = (rows, *item[1:])
        elif isinstance(item, pl.Series):
            item = item.to_pandas()
        return self._df.to_pandas().loc[item]


if not hasattr(pl.Series, "iloc"):
    pl.Series.iloc = property(lambda self: self)  # type: ignore[attr-defined]
if not hasattr(pl.Series, "isna"):
    pl.Series.isna = lambda self: self.is_null()  # type: ignore[attr-defined]
if not hasattr(pl.Series, "isnull"):
    pl.Series.isnull = lambda self: self.is_null()  # type: ignore[attr-defined]
if not hasattr(pl.Series, "tolist"):
    pl.Series.tolist = pl.Series.to_list  # type: ignore[attr-defined]

_orig_datatype_eq = pl.DataType.__eq__


def _compat_datatype_eq(self: pl.DataType, other: Any) -> bool:
    if _orig_datatype_eq(self, other):
        return True
    if isinstance(other, str):
        name = self.__class__.__name__.lower()
        other_clean = other.lower().replace("dtype", "")
        return other_clean in (name, f"pl.{name}")
    return False


pl.DataType.__eq__ = _compat_datatype_eq


class DataFrame:
    """High-performance tabular data frame powered by Polars, exposing Pytae's fluent grammar."""

    def __init__(self, data: Any = None, orig_col_map: dict[str, Any] | None = None) -> None:
        self._orig_col_map: dict[str, Any] = dict(orig_col_map) if orig_col_map else {}
        self._col_collisions: set[str] = set()
        self._orig_index: list[Any] | None = list(data.index) if hasattr(data, "index") else None

        def _detect_collisions(pdf: Any) -> set[str]:
            collisions = set()
            for col in pdf.columns:
                if pdf[col].dtype == object:
                    vals = pdf[col].tolist()
                    import pandas as pd

                    str_vals = ["nan" if pd.isna(x) else str(x) for x in vals]
                    if len(set(vals)) != len(set(str_vals)):
                        collisions.add(str(col))
            return collisions

        if isinstance(data, (pl.DataFrame, pl.LazyFrame)):
            self._df = data
        elif isinstance(data, DataFrame):
            self._df = data._df
            if not self._orig_col_map:
                self._orig_col_map = dict(data._orig_col_map)
            self._col_collisions = set(data._col_collisions)
            self._orig_index = data._orig_index
        elif isinstance(data, GroupedDataFrame):
            self._df = data._df
            self._orig_index = data._orig_index
        elif hasattr(data, "to_pandas") and not isinstance(data, (str, Path)):
            try:
                import pandas as pd

                if isinstance(data, pd.DataFrame):
                    self._orig_col_map = {str(c): c for c in data.columns}
                    self._col_collisions = _detect_collisions(data)
                    self._orig_index = list(data.index)
                    try:
                        self._df = pl.from_pandas(data)
                    except Exception:
                        df_c = data.copy()
                        for col in df_c.columns:
                            if df_c[col].dtype == object:
                                df_c[col] = df_c[col].astype(str)
                        self._df = pl.from_pandas(df_c)
                else:
                    pdf = data.to_pandas()
                    self._orig_col_map = {str(c): c for c in pdf.columns}
                    self._col_collisions = _detect_collisions(pdf)
                    self._orig_index = list(pdf.index)
                    try:
                        self._df = pl.from_pandas(pdf)
                    except Exception:
                        df_c = pdf.copy()
                        for col in df_c.columns:
                            if df_c[col].dtype == object:
                                df_c[col] = df_c[col].astype(str)
                        self._df = pl.from_pandas(df_c)
            except Exception:
                self._df = pl.DataFrame(data)
        elif data is None:
            self._df = pl.DataFrame()
        else:
            try:
                import pandas as pd

                if isinstance(data, pd.DataFrame):
                    self._orig_col_map = {str(c): c for c in data.columns}
                    self._col_collisions = _detect_collisions(data)
                    self._orig_index = list(data.index)
                    try:
                        self._df = pl.from_pandas(data)
                    except Exception:
                        df_c = data.copy()
                        for col in df_c.columns:
                            if df_c[col].dtype == object:
                                df_c[col] = df_c[col].astype(str)
                        self._df = pl.from_pandas(df_c)
                else:
                    self._df = pl.DataFrame(data)
            except Exception:
                self._df = pl.DataFrame(data)

    # -------------------------------------------------------------------------
    # Core Properties & Representation
    # -------------------------------------------------------------------------

    @property
    def pt(self) -> DataFrame:
        """Allow fluid chaining whether or not .pt is repeated."""
        return self

    @property
    def is_lazy(self) -> bool:
        """Return True if this DataFrame is backed by a lazy Polars execution plan."""
        return isinstance(self._df, pl.LazyFrame)

    def lazy(self) -> DataFrame:
        """Convert eager DataFrame to a lazy execution plan."""
        if isinstance(self._df, pl.LazyFrame):
            return self
        return DataFrame(self._df.lazy(), orig_col_map=self._orig_col_map)

    def collect(self, **kwargs: Any) -> DataFrame:
        """Execute the lazy plan and materialize into an eager DataFrame."""
        if isinstance(self._df, pl.LazyFrame):
            return DataFrame(self._df.collect(**kwargs), orig_col_map=self._orig_col_map)
        return self

    def explain(self, *args: Any, **kwargs: Any) -> str:
        """Return the unoptimized or optimized physical plan as a string."""
        if isinstance(self._df, pl.LazyFrame):
            return self._df.explain(*args, **kwargs)
        return self._df.lazy().explain(*args, **kwargs)

    @property
    def attrs(self) -> dict[str, Any]:
        """Custom metadata attribute dictionary."""
        return {}

    @property
    def shape(self) -> tuple[int, int]:
        if self.is_lazy:
            n_rows = self._df.select(pl.len()).collect().item()
            n_cols = len(self._df.collect_schema().names())
            return (n_rows, n_cols)
        return self._df.shape

    @property
    def columns(self) -> ColumnNames:
        cols = self._df.collect_schema().names() if self.is_lazy else self._df.columns
        if self._orig_col_map:
            return ColumnNames([self._orig_col_map.get(c, c) for c in cols])
        return ColumnNames(cols)

    @property
    def dtypes(self) -> list[pl.DataType]:
        if self.is_lazy:
            return list(self._df.collect_schema().values())
        return list(self._df.dtypes)

    @property
    def schema(self) -> pl.Schema:
        if self.is_lazy:
            return self._df.collect_schema()
        return self._df.schema

    @property
    def index(self) -> Any:
        return self._orig_index if self._orig_index is not None else range(len(self))

    @property
    def iloc(self) -> _IlocIndexer:
        return _IlocIndexer(self)

    @property
    def loc(self) -> _LocIndexer:
        return _LocIndexer(self)

    def copy(self, deep: bool = True) -> DataFrame:
        df = DataFrame(self._df.clone(), orig_col_map=self._orig_col_map)
        df._orig_index = list(self._orig_index) if self._orig_index is not None else None
        df._col_collisions = set(self._col_collisions)
        return df

    def clone(self) -> DataFrame:
        return self.copy()

    def equals(self, other: Any) -> bool:
        if isinstance(other, DataFrame):
            return self._df.equals(other._df)
        try:
            return self.to_pandas().equals(other)
        except Exception:
            return False

    @property
    def values(self) -> Any:
        return self._df.to_numpy()

    def to_numpy(self, *args: Any, **kwargs: Any) -> Any:
        return self._df.to_numpy(*args, **kwargs)

    def select_dtypes(self, *args: Any, **kwargs: Any) -> DataFrame:
        """Filter columns based on data types."""
        from pytae.select import _matches_dtype

        include = kwargs.get("include", args[0] if len(args) > 0 else None)
        exclude = kwargs.get("exclude", args[1] if len(args) > 1 else None)
        matched = list(self.columns)
        schema = self._df.schema
        if include is not None:
            matched = [c for c in matched if _matches_dtype(schema[c], include)]
        if exclude is not None:
            matched = [c for c in matched if not _matches_dtype(schema[c], exclude)]
        return self.select(*matched)

    def safe_reset_index(self) -> DataFrame:
        """Polars DataFrames have no index; returns self."""
        return self

    def isna(self) -> Any:
        """Check for missing values, delegating to Pandas for 100% API compatibility."""
        return self.to_pandas().isna()

    def isnull(self) -> Any:
        """Alias for isna()."""
        return self.to_pandas().isnull()

    def sort_values(
        self,
        by: Any = None,
        ascending: bool = True,
        na_position: str = "last",
        **kwargs: Any,
    ) -> DataFrame:
        """Pandas-compatible sort_values, delegating to Polars sort."""
        descending = not ascending if isinstance(ascending, bool) else [not a for a in ascending]
        nulls_last = na_position == "last"
        by_cols = [by] if isinstance(by, str) else list(by)
        return DataFrame(self._df.sort(by_cols, descending=descending, nulls_last=nulls_last))

    def query(self, *conditions: Any, **kwargs: Any) -> DataFrame:
        """Pandas-compatible query(), delegating to Pytae filter()."""
        return self.filter(*conditions, **kwargs)

    def slice_max(self, *args: Any, **kwargs: Any) -> None:
        raise AttributeError("df.pt.slice_max() has been removed; use df.pt.pick() instead")

    def slice_min(self, *args: Any, **kwargs: Any) -> None:
        raise AttributeError("df.pt.slice_min() has been removed; use df.pt.pick(..., order='min') instead")

    def agg_df(self, *args: Any, **kwargs: Any) -> None:
        raise AttributeError("df.pt.agg_df() has been removed; use df.pt.agg() instead")

    def __len__(self) -> int:
        if self.is_lazy:
            return self._df.select(pl.len()).collect().item()
        return len(self._df)

    def __iter__(self) -> Any:
        return iter(self.columns)

    def __getitem__(self, item: Any) -> Any:
        if self.is_lazy:
            if isinstance(item, str):
                return DataFrame(self._df.select(item))
            if isinstance(item, (list, tuple)):
                return DataFrame(self._df.select(list(item)))
            return DataFrame(self._df.select(item))
        if isinstance(item, pl.Series) and item.dtype == pl.Boolean:
            return DataFrame(self._df.filter(item), orig_col_map=self._orig_col_map)
        if isinstance(item, (list, tuple)) and item and isinstance(item[0], bool):
            return DataFrame(self._df.filter(pl.Series(item)), orig_col_map=self._orig_col_map)
        col_key = (
            str(item) if not isinstance(item, (pl.Series, list, tuple)) and str(item) in self._df.columns else item
        )
        if isinstance(col_key, int) and col_key not in self._df.columns:
            raise KeyError(col_key)
        res = self._df[col_key]
        if isinstance(res, pl.DataFrame):
            return DataFrame(res, orig_col_map=self._orig_col_map)
        return res

    def __repr__(self) -> str:
        return repr(self._df)

    def _repr_html_(self) -> str:
        if self.is_lazy:
            return f"<pre>{self.explain()}</pre>"
        return self._df._repr_html_()

    def head(self, n: int = 5) -> DataFrame:
        return DataFrame(self._df.head(n))

    def tail(self, n: int = 5) -> DataFrame:
        return DataFrame(self._df.tail(n))

    def sample(
        self,
        n: int | None = None,
        frac: float | None = None,
        *,
        fraction: float | None = None,
        seed: int | None = None,
        random_state: int | None = None,
        with_replacement: bool = False,
        replace: bool = False,
        shuffle: bool = False,
    ) -> DataFrame:
        """Randomly sample rows from the DataFrame.

        Parameters
        ----------
        n : int, optional
            Number of rows to sample. Defaults to 5 if neither n nor frac/fraction is provided.
        frac, fraction : float, optional
            Fraction of axis items to return (0.0 to 1.0).
        seed, random_state : int, optional
            Seed for reproducible random sampling.
        with_replacement, replace : bool, default False
            Allow sampling with replacement.
        shuffle : bool, default False
            Whether to shuffle the sampled rows.
        """
        effective_frac = frac if frac is not None else fraction
        effective_seed = seed if seed is not None else random_state
        effective_replace = with_replacement or replace

        eager_df = self._df.collect() if self.is_lazy else self._df
        if effective_frac is not None:
            sampled = eager_df.sample(
                fraction=effective_frac,
                with_replacement=effective_replace,
                shuffle=shuffle,
                seed=effective_seed,
            )
        else:
            n_val = 5 if n is None else n
            n_rows = len(eager_df)
            sample_n = min(n_val, n_rows) if not effective_replace else n_val
            sampled = (
                eager_df.sample(
                    n=sample_n,
                    with_replacement=effective_replace,
                    shuffle=shuffle,
                    seed=effective_seed,
                )
                if sample_n > 0
                else eager_df.head(0)
            )
        return DataFrame(sampled, orig_col_map=self._orig_col_map)

    def __getattr__(self, name: str) -> Any:
        # Do not intercept private/dunder attributes or if _df is not yet initialized
        if name.startswith("_") or not hasattr(self, "_df"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        try:
            attr = getattr(self._df, name)
        except AttributeError:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'") from None

        if callable(attr):

            def _polars_method_wrapper(*args: Any, **kwargs: Any) -> Any:
                clean_args = [
                    a._df
                    if isinstance(a, DataFrame)
                    else (a.to_polars() if hasattr(a, "to_polars") and not isinstance(a, (str, Path)) else a)
                    for a in args
                ]
                clean_kwargs = {
                    k: (
                        v._df
                        if isinstance(v, DataFrame)
                        else (v.to_polars() if hasattr(v, "to_polars") and not isinstance(v, (str, Path)) else v)
                    )
                    for k, v in kwargs.items()
                }
                res = attr(*clean_args, **clean_kwargs)
                if isinstance(res, (pl.DataFrame, pl.LazyFrame)):
                    return DataFrame(res)
                return res

            return _polars_method_wrapper
        return attr

    def join(
        self,
        other: Any,
        on: str | Sequence[str] | None = None,
        how: str = "inner",
        *,
        left_on: str | Sequence[str] | None = None,
        right_on: str | Sequence[str] | None = None,
        suffix: str = "_right",
        suffixes: tuple[str, str] | None = None,
        validate: str = "m:m",
        coalesce: bool | None = None,
        **kwargs: Any,
    ) -> DataFrame:
        """Join this DataFrame with another tabular dataset using native Polars multithreading.

        Parameters
        ----------
        other : DataFrame | pl.DataFrame | pd.DataFrame | pl.LazyFrame | Any
            The other table to join with.
        on : str | Sequence[str] | None
            Join key column(s). Can be a single column string, comma-separated string,
            list of columns, or colon-delimited mapping (e.g. ``"id:user_id"``).
            If omitted and ``left_on``/``right_on`` are not specified, joins on common columns.
        how : str, default "inner"
            Type of join: ``"inner"``, ``"left"``, ``"right"``, ``"full"``,
            ``"semi"``, ``"anti"``, or ``"cross"``.
        left_on : str | Sequence[str] | None
            Key column(s) in the left table.
        right_on : str | Sequence[str] | None
            Key column(s) in the right table.
        suffix : str, default "_right"
            Suffix added to overlapping column names in the right frame.
        suffixes : tuple[str, str] | None, default None
            Suffixes added to overlapping column names: ``(left_suffix, right_suffix)``.
        validate : str, default "m:m"
            Validation check: ``"1:1"``, ``"1:m"``, ``"m:1"``, or ``"m:m"``.
        coalesce : bool | None, default None
            Whether to coalesce join keys. Defaults to True when keys match, or False
            when ``left_on != right_on`` to preserve both keys.

        Returns
        -------
        DataFrame
            Joined Pytae DataFrame. Retains lazy execution if both frames are lazy.
        """
        res = join_polars(
            self._df,
            other,
            on=on,
            how=how,
            left_on=left_on,
            right_on=right_on,
            suffix=suffix,
            suffixes=suffixes,
            validate=validate,
            coalesce=coalesce,
            **kwargs,
        )
        return DataFrame(res)

    def concat(
        self,
        *others: Any,
        how: str = "vertical",
        axis: int | str | None = None,
        **kwargs: Any,
    ) -> DataFrame:
        """Concatenate this DataFrame with one or more other DataFrames vertically or horizontally.

        Parameters
        ----------
        *others : Any
            One or more DataFrames, Polars DataFrames, or Pandas DataFrames to stack.
        how : str, default "vertical"
            Concatenation strategy: ``"vertical"`` (stacks rows; falls back to ``"diagonal_relaxed"`` if
            schemas differ), ``"horizontal"``, ``"diagonal"``, or ``"diagonal_relaxed"``.
        axis : int | str | None, default None
            ``0`` or ``"vertical"`` for rows, ``1`` or ``"horizontal"`` for columns.

        Returns
        -------
        DataFrame
            Concatenated Pytae DataFrame.
        """
        all_dfs = [self._df, *others]
        res = concat_polars(all_dfs, how=how, axis=axis, **kwargs)
        return DataFrame(res)

    # -------------------------------------------------------------------------
    # Fluent Transformation Verbs
    # -------------------------------------------------------------------------

    def filter(self, *conditions: Any, **kwargs: Any) -> DataFrame:
        """Filter rows using conditions (string expressions, callables, or kwargs)."""
        if any(callable(c) for c in conditions):
            if kwargs or len(conditions) > 1:
                raise TypeError("callable/lambda predicates cannot be mixed with other filter arguments")
            cond = conditions[0]
            eager_self = self.collect() if self.is_lazy else self
            mask = cond(eager_self)
            if isinstance(mask, pl.Series):
                return DataFrame(eager_self._df.filter(mask))
            elif hasattr(mask, "values"):
                return DataFrame(eager_self._df.filter(pl.Series(mask.values)))
            else:
                return DataFrame(eager_self._df.filter(pl.Series(list(mask))))

        cond_pairs: list[tuple[str, Any]] = []
        for cond in conditions:
            if isinstance(cond, str):
                cond_pairs.extend(_parse_filter_string(cond))
            elif isinstance(cond, dict):
                cond_pairs.extend(cond.items())
            elif isinstance(cond, (list, tuple)) and cond and isinstance(cond[0], tuple):
                cond_pairs.extend(cond)  # type: ignore[arg-type]
            elif isinstance(cond, tuple) and len(cond) == 2:
                cond_pairs.append(cond)  # type: ignore[arg-type]

        for k, v in kwargs.items():
            cond_pairs.append((k, v))

        return DataFrame(filter_polars(self._df, cond_pairs))

    def select(self, *names: Any, **kwargs: Any) -> DataFrame:
        """Select, reorder, slice, and drop columns using Pytae selection grammar."""
        return DataFrame(select_polars(self._df, list(names), kwargs), orig_col_map=self._orig_col_map)

    def arrange(self, *specs: str, na_last: bool = True) -> DataFrame:
        """Sort rows by one or more column expressions (e.g. 'col1, -col2 desc')."""
        spec_str = ",".join(specs)
        return DataFrame(arrange_polars(self._df, spec_str, na_last=na_last))

    def distinct(self, *cols: Any, keep: str = "first") -> DataFrame:
        """Deduplicate rows across all or specific columns with keep='first'|'last'|'none'."""
        for c in cols:
            if isinstance(c, (list, tuple, set)):
                raise TypeError(
                    f"distinct() takes column names as positional arguments, e.g. distinct('a', 'b'). "
                    f"Lists are not accepted, got {type(c).__name__}."
                )
        if cols:
            avail = set(self.columns)
            missing = [str(c) for c in cols if str(c) not in avail]
            if missing:
                raise KeyError(f"distinct: column(s) {missing} not found in DataFrame")
        return DataFrame(distinct_polars(self._df, list(cols), keep=keep))

    def dropna(self, *cols: Any, subset: Any = None, how: str | None = None, drop_nans: bool = True) -> DataFrame:
        """Drop rows containing missing values (Arrow null and/or float NaN).

        Option B Zero Data Loss Philosophy:
        - Without arguments: drops completely empty rows (all columns null/NaN, how='all').
        - With column names: drops rows where any of the specified columns are null/NaN (how='any').
        - Pass how='any' or how='all' to explicitly override.
        - drop_nans=True (default) drops float NaNs in addition to Arrow nulls.
        """
        resolved = list(subset) if subset is not None else (list(cols) if cols else None)
        return DataFrame(dropna_polars(self._df, cols=resolved, how=how, drop_nans=drop_nans))

    def drop_nulls(self, *cols: Any, subset: Any = None, how: str | None = None, drop_nans: bool = True) -> DataFrame:
        """Alias for dropna()."""
        return self.dropna(*cols, subset=subset, how=how, drop_nans=drop_nans)

    def drop_na(self, *cols: Any, subset: Any = None, how: str | None = None, drop_nans: bool = True) -> DataFrame:
        """Alias for dropna()."""
        return self.dropna(*cols, subset=subset, how=how, drop_nans=drop_nans)

    def fillna(self, value: Any = None, *cols: Any, subset: Any = None, nans: bool = True) -> DataFrame:
        """Fill missing values (Arrow null and/or float NaN).

        Parameters
        ----------
        value : scalar or dict
            Fill value. If a dictionary is provided, maps column names to fill values.
        *cols : str
            Column names to fill (if value is a scalar).
        subset : sequence of str, optional
            Alternative way to specify columns.
        nans : bool, default True
            If True, cleans both float NaN and Arrow null on numeric columns.
            If False, only replaces Arrow null.
        """
        if cols or subset is not None:
            target = list(subset) if subset is not None else list(cols)
            avail = set(self.columns)
            missing = [str(c) for c in target if str(c) not in avail]
            if missing:
                raise KeyError(f"fillna: column(s) {missing} not found in DataFrame")
        return DataFrame(fillna_polars(self._df, value, *cols, subset=subset, nans=nans))

    def fill_null(self, value: Any = None, *cols: Any, subset: Any = None) -> DataFrame:
        """Alias for fillna(..., nans=False) targeting Arrow nulls only."""
        return self.fillna(value, *cols, subset=subset, nans=False)

    def fill_nan(self, value: Any = None, *cols: Any, subset: Any = None) -> DataFrame:
        """Fill only float NaNs, leaving Arrow nulls unchanged."""
        if cols or subset is not None:
            target = list(subset) if subset is not None else list(cols)
            avail = set(self.columns)
            missing = [str(c) for c in target if str(c) not in avail]
            if missing:
                raise KeyError(f"fill_nan: column(s) {missing} not found in DataFrame")
        return DataFrame(fill_nan_polars(self._df, value, *cols, subset=subset))

    def cast(self, dtypes: Any = None, strict: bool = True, **kwargs: Any) -> DataFrame:
        """Cast column types using Polars native SIMD vectorization.

        Parameters
        ----------
        dtypes : Mapping or str, optional
            Mapping of column names to target types (e.g. {'x': int, 'y': float})
            or comma-separated string specification (e.g. 'x:int, y:float').
        strict : bool, default True
            Whether to raise an error on invalid type conversions or return nulls.
        **kwargs : Any
            Additional column-to-type assignments (e.g. x=int, y='float').
        """
        return DataFrame(cast_polars(self._df, dtypes=dtypes, strict=strict, **kwargs))

    def diff(
        self,
        other: Any,
        tol: float = 0.0,
        rtol: float = 0.0,
    ) -> str:
        """Compare schema and contents against another DataFrame or dataset file with optional tolerance.

        Parameters
        ----------
        other : DataFrame, pl.DataFrame, pd.DataFrame, str, or Path
            Dataset or file path to compare against.
        tol : float, default 0.0
            Absolute numeric threshold / tolerance for numeric comparisons.
        rtol : float, default 0.0
            Relative numeric threshold / tolerance for numeric comparisons.

        Returns
        -------
        str
            A structured human-readable comparison report.
        """
        from pytae.cli_run import _compute_diff

        left_df = self.to_pandas()
        return _compute_diff(left_df, other, "<left>", tol=tol, rtol=rtol)

    def pick(
        self,
        spec: str,
        n: int | None = None,
        prop: float | None = None,
        order: str = "max",
        with_ties: bool = False,
        na_last: bool = True,
    ) -> DataFrame:
        """Select top/bottom rows by column expression (replaces slice_max/slice_min)."""
        return DataFrame(
            pick_polars(
                self._df,
                spec,
                by=None,
                n=n,
                prop=prop,
                order=order,
                with_ties=with_ties,
                na_last=na_last,
            )
        )

    def by(self, *cols: Any) -> GroupedDataFrame:
        """Establish a grouping context for subsequent .mutate(), .agg(), or .pick() operations."""
        if not cols:
            raise ValueError("df.pt.by() takes at least one column name")
        for c in cols:
            if c is None:
                raise TypeError("df.pt.by(None) is not supported")
            if isinstance(c, (list, tuple, set)):
                raise TypeError(
                    f"df.pt.by() takes column names as positional arguments, e.g. df.pt.by('a', 'b'). "
                    f"Lists are not accepted, got {type(c).__name__}."
                )
        resolved: list[str] = []
        for c in cols:
            if isinstance(c, str):
                if "," in c:
                    resolved.extend([_unquote_name(part.strip()) for part in c.split(",") if part.strip()])
                else:
                    resolved.append(_unquote_name(c.strip()))
            else:
                resolved.append(str(c))
        return GroupedDataFrame(self._df, resolved, orig_col_map=self._orig_col_map, orig_index=self._orig_index)

    def mutate(self, *specs: Any, **kwargs: Any) -> DataFrame:
        """Create or transform columns using vectorized expressions, math, if_else, map, shift."""
        if "by" in kwargs or "_by" in kwargs:
            raise TypeError(
                "df.pt.mutate() does not accept 'by'. Set grouping beforehand using pt.by(df, 'col') or df.pt.by('col')."
            )

        if not specs and not kwargs:
            raise ValueError(
                'mutate() expects at least one column specification (kwargs or string expressions), e.g. "col = expr"'
            )

        import inspect

        _here = inspect.currentframe()
        caller_frame = None if _here is None else _here.f_back
        del _here
        while caller_frame is not None:
            name = caller_frame.f_globals.get("__name__") or ""
            if name != "pytae" and not name.startswith("pytae."):
                break
            caller_frame = caller_frame.f_back
        frame_vars: dict[str, Any] = {}
        if caller_frame is not None:
            frame_vars.update(caller_frame.f_globals)
            frame_vars.update(caller_frame.f_locals)
        del caller_frame

        params = kwargs.pop("_params", None)
        if params is None and "params" in kwargs and isinstance(kwargs["params"], dict):
            params = kwargs.pop("params")

        merged_params = dict(frame_vars)
        if params:
            merged_params.update(params)

        steps: list[tuple[str, Any]] = []
        current_spec: dict[str, Any] = {}

        for s in specs:
            if isinstance(s, str):
                entries = _parse_mutate_spec_entries(s)
                for k, v, _ in entries:
                    current_spec[k] = v
            elif isinstance(s, dict):
                for k, v in s.items():
                    current_spec[str(k)] = v
            elif callable(s):
                raise TypeError(
                    "mutate() expects callables as keyword arguments with the column name, "
                    "e.g. df.pt.mutate(new_col=lambda d: d['x'] * 2)"
                )
            else:
                raise TypeError(f"mutate() received unexpected positional argument of type {type(s).__name__}.")

        for k, v in kwargs.items():
            if callable(v):
                if current_spec:
                    steps.append(("spec", current_spec))
                    current_spec = {}
                steps.append(("callable", (k, v)))
            else:
                current_spec[k] = v

        if current_spec:
            steps.append(("spec", current_spec))

        res = self
        for step_type, step_data in steps:
            if step_type == "spec":
                res_df = mutate_polars(res._df, step_data, by=None, params=merged_params) if step_data else res._df
                res = DataFrame(res_df, orig_col_map=res._orig_col_map)
                res._orig_index = self._orig_index
            elif step_type == "callable":
                col_name, fn = step_data
                col_res = fn(res)
                if isinstance(col_res, (pl.Series, pl.Expr)):
                    new_series = col_res.alias(col_name)
                elif hasattr(col_res, "to_numpy"):
                    new_series = pl.Series(col_name, col_res.to_numpy())
                else:
                    new_series = pl.Series(col_name, list(col_res))
                new_map = dict(res._orig_col_map)
                new_map[col_name] = col_name
                res = DataFrame(res._df.with_columns(new_series), orig_col_map=new_map)
                res._orig_index = self._orig_index

        return res

    def rename(self, *args: Any, columns: dict[str, str] | None = None, **kwargs: Any) -> DataFrame:
        """Rename columns using mapping dictionary or columns keyword argument."""
        mapping: dict[str, str] = {}
        if args and isinstance(args[0], dict):
            mapping.update(args[0])
        if columns:
            mapping.update(columns)
        if kwargs:
            mapping.update(kwargs)
        new_df = self._df.rename(mapping)
        new_col_map = dict(self._orig_col_map)
        for old, new in mapping.items():
            new_col_map[new] = new
        res = DataFrame(new_df, orig_col_map=new_col_map)
        res._orig_index = self._orig_index
        return res

    def agg(self, *specs: Any, a: Any = None, dropna: bool = False, **kwargs: Any) -> DataFrame:
        """Aggregate numeric columns or compute custom metrics across the whole DataFrame."""
        if "by" in kwargs or "_by" in kwargs:
            raise TypeError(
                "df.pt.agg() does not accept 'by'. Set grouping beforehand using pt.by(df, 'col') or df.pt.by('col')."
            )
        return DataFrame(agg_polars(self._df, *specs, by=None, a=a, dropna=dropna, **kwargs))

    def pivot(
        self,
        r: str | Sequence[str] | None = None,
        c: str | Sequence[str] | None = None,
        v: str | Sequence[str] | None = None,
        a: str = "sum",
        dropna: bool = False,
        f_v: Any = None,
        **kwargs: Any,
    ) -> DataFrame:
        """Compute multi-dimensional cross-tabulations and pivot tables."""
        c_list = [c] if isinstance(c, str) else (list(c) if c else [])
        for col in c_list:
            if str(col) in self._col_collisions:
                raise ValueError("Pivoting would result in column headers that contain duplicate names")
        return DataFrame(
            pivot_polars(self._df, r=r, c=c, v=v, a=a, dropna=dropna, f_v=f_v, _func_name="pivot", **kwargs)
        )

    def long(
        self,
        cols: str | Sequence[str] | None = None,
        id_vars: str | Sequence[str] | None = None,
        c: str = "variable",
        v: str = "value",
    ) -> DataFrame:
        """Reshape DataFrame from wide to long format (unpivot/melt)."""
        return DataFrame(long_polars(self._df, cols=cols, id_vars=id_vars, c=c, v=v))

    def wide(
        self,
        r: str | Sequence[str] | None = None,
        c: str = "variable",
        v: str = "value",
        **kwargs: Any,
    ) -> DataFrame:
        """Reshape DataFrame from long to wide format (1-to-1 un-melt)."""
        return DataFrame(wide_polars(self._df, r=r, c=c, v=v, **kwargs))

    def clean_columns(
        self,
        *,
        strip: bool = False,
        strip_special: bool = False,
        squeeze: bool = False,
        fill: str | None = None,
        case: str | None = None,
        dedupe: bool = False,
    ) -> DataFrame:
        """Clean and normalize column header names."""
        return DataFrame(
            clean_columns_polars(
                self._df,
                strip=strip,
                strip_special=strip_special,
                squeeze=squeeze,
                fill=fill,
                case=case,
                dedupe=dedupe,
            )
        )

    def replace_values(
        self,
        v: dict[Any, Any],
        c: str | Sequence[str] | None = None,
        exact: bool = True,
    ) -> DataFrame:
        """Replace exact values or substrings across columns."""
        return DataFrame(
            replace_values_polars(
                self._df,
                v=v,
                c=c,
                exact=exact,
            )
        )

    def handle_missing(
        self,
        fillna: str | None = ".",
        numeric_fill: Any = 0,
        cols: Sequence[str] | None = None,
        preserve_categories: bool = True,
        **kwargs: Any,
    ) -> DataFrame:
        """Fill null values with type-appropriate defaults."""
        return DataFrame(
            handle_missing_polars(
                self._df,
                fillna=fillna,
                numeric_fill=numeric_fill,
                cols=cols,
                preserve_categories=preserve_categories,
                **kwargs,
            )
        )

    def cols(self, ascending: bool | None = True) -> list[str]:
        """Return sorted or natural column names."""
        columns = list(self.columns)
        if ascending is True:
            return sorted(columns)
        elif ascending is False:
            return sorted(columns, reverse=True)
        elif ascending is None:
            return columns
        else:
            raise ValueError(f"Invalid ascending value '{ascending}'. Must be True, False, or None")

    def glimpse(self, width: int | None = None) -> DataFrame:
        """Print an R tibble / tidyverse-style schema and preview of the DataFrame."""
        from pytae.other_utilities import format_glimpse

        print(format_glimpse(self, width=width))
        return self

    def freq(self, col: str | None = None, dropna: bool = False) -> DataFrame:
        """Calculate frequency distribution of unique column values."""
        from pytae.other_utilities import freq as _freq

        return DataFrame(_freq(self.to_pandas(), col=col, dropna=dropna))

    def hist(self, col: str | None = None, bins: int = 10) -> DataFrame:
        """Compute a binned distribution histogram with ASCII bars and percentages for a numeric column."""
        from pytae.other_utilities import hist as _hist

        return DataFrame(_hist(self.to_pandas(), col=col, bins=bins))

    def pipe(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Apply a callable function taking DataFrame as its first argument."""
        return func(self, *args, **kwargs)

    # -------------------------------------------------------------------------
    # Interop & Export
    # -------------------------------------------------------------------------

    def to_pandas(self, *args: Any, **kwargs: Any) -> Any:
        """Convert to pandas DataFrame, preserving tracked index and column metadata."""
        import pandas as pd

        eager_df = self._df.collect() if self.is_lazy else self._df
        pdf = eager_df.to_pandas(*args, **kwargs)
        if self._orig_index is not None and len(self._orig_index) == len(pdf):
            pdf.index = pd.Index(self._orig_index)
        if self._orig_col_map:
            pdf.columns = [self._orig_col_map.get(c, c) for c in pdf.columns]
        return pdf

    def to_polars(self) -> pl.DataFrame:
        """Extract the underlying Polars DataFrame (collecting if lazy)."""
        if self.is_lazy:
            return self._df.collect()
        return self._df

    def to_clip(self) -> None:
        """Copy DataFrame to system clipboard via TSV without index."""
        eager_df = self._df.collect() if self.is_lazy else self._df
        tsv_str = eager_df.write_csv(separator="\t")
        system = platform.system()
        try:
            if system == "Darwin":
                p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                p.communicate(tsv_str.encode("utf-8"))
            elif system == "Windows":
                p = subprocess.Popen(["clip"], stdin=subprocess.PIPE)
                p.communicate(tsv_str.encode("utf-8"))
            else:
                p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                p.communicate(tsv_str.encode("utf-8"))
        except Exception:
            self.to_pandas().to_clipboard(index=False)

    def to_parquet(self, path: str | Path, **kwargs: Any) -> None:
        kwargs.pop("index", None)
        if self.is_lazy:
            try:
                self._df.sink_parquet(path, **kwargs)
                return
            except Exception:
                self._df.collect().write_parquet(path, **kwargs)
                return
        self._df.write_parquet(path, **kwargs)

    def to_csv(self, path: str | Path, **kwargs: Any) -> None:
        kwargs.pop("index", None)
        if self.is_lazy:
            try:
                self._df.sink_csv(path, **kwargs)
                return
            except Exception:
                self._df.collect().write_csv(path, **kwargs)
                return
        self._df.write_csv(path, **kwargs)

    def plot(self, *args: Any, **kwargs: Any) -> Any:
        """Create visualizations using Pytae Plotter."""
        return _plot_impl(self.to_pandas(), *args, **kwargs)


class GroupedDataFrame:
    """A lazy grouped container backed by a Polars DataFrame or LazyFrame and grouping key columns."""

    def __init__(
        self,
        df: Any,
        by_cols: list[str],
        orig_col_map: dict[str, Any] | None = None,
        orig_index: Any = None,
    ) -> None:
        self._df = df
        self._by = by_cols
        self._orig_col_map = orig_col_map or {}
        self._orig_index = orig_index

    @property
    def pt(self) -> GroupedDataFrame:
        """Allow fluid chaining whether or not .pt is repeated."""
        return self

    @property
    def attrs(self) -> dict[str, Any]:
        return {"_pt_by": tuple(self._by)}

    def by(self, *cols: Any) -> GroupedDataFrame:
        """Overwrite grouping with new keys."""
        return DataFrame(self._df, orig_col_map=self._orig_col_map).by(*cols)

    def ungroup(self) -> DataFrame:
        """Remove grouping context and return a standard DataFrame."""
        res = DataFrame(self._df, orig_col_map=self._orig_col_map)
        res._orig_index = self._orig_index
        return res

    def to_pandas(self) -> Any:
        import pandas as pd

        pdf = self._df.to_pandas()
        if self._orig_index is not None and len(self._orig_index) == len(pdf):
            pdf.index = pd.Index(self._orig_index)
        return pdf

    def mutate(self, *specs: Any, **kwargs: Any) -> DataFrame:
        """Calculate windowed mutations across the established groups."""
        if "by" in kwargs or "_by" in kwargs:
            raise TypeError(
                "df.pt.mutate() does not accept 'by'. Set grouping beforehand using pt.by(df, 'col') or df.pt.by('col')."
            )

        if not specs and not kwargs:
            raise ValueError(
                'mutate() expects at least one column specification (kwargs or string expressions), e.g. "col = expr"'
            )

        dropna = kwargs.pop("dropna", False)

        import inspect

        _here = inspect.currentframe()
        caller_frame = None if _here is None else _here.f_back
        del _here
        while caller_frame is not None:
            name = caller_frame.f_globals.get("__name__") or ""
            if name != "pytae" and not name.startswith("pytae."):
                break
            caller_frame = caller_frame.f_back
        frame_vars: dict[str, Any] = {}
        if caller_frame is not None:
            frame_vars.update(caller_frame.f_globals)
            frame_vars.update(caller_frame.f_locals)
        del caller_frame

        params = kwargs.pop("_params", None)
        if params is None and "params" in kwargs and isinstance(kwargs["params"], dict):
            params = kwargs.pop("params")

        merged_params = dict(frame_vars)
        if params:
            merged_params.update(params)

        steps: list[tuple[str, Any]] = []
        current_spec: dict[str, Any] = {}

        for s in specs:
            if isinstance(s, str):
                entries = _parse_mutate_spec_entries(s)
                for k, v, _ in entries:
                    current_spec[k] = v
            elif isinstance(s, dict):
                for k, v in s.items():
                    current_spec[str(k)] = v
            elif callable(s):
                raise TypeError(
                    "mutate() expects callables as keyword arguments with the column name, "
                    "e.g. df.pt.mutate(new_col=lambda d: d['x'] * 2)"
                )
            else:
                raise TypeError(f"mutate() received unexpected positional argument of type {type(s).__name__}.")

        for k, v in kwargs.items():
            if callable(v):
                if current_spec:
                    steps.append(("spec", current_spec))
                    current_spec = {}
                steps.append(("callable", (k, v)))
            else:
                current_spec[k] = v

        if current_spec:
            steps.append(("spec", current_spec))

        res = DataFrame(self._df, orig_col_map=self._orig_col_map)
        res._orig_index = self._orig_index

        for step_type, step_data in steps:
            if step_type == "spec":
                res_df = (
                    mutate_polars(res._df, step_data, by=self._by, params=merged_params, dropna=dropna)
                    if step_data
                    else res._df
                )
                res = DataFrame(res_df, orig_col_map=res._orig_col_map)
                res._orig_index = self._orig_index
            elif step_type == "callable":
                col_name, fn = step_data
                pdf = res.to_pandas()
                pieces = []
                for _, group in pdf.groupby(self._by, sort=False, dropna=dropna):
                    import pandas as pd

                    part_res = fn(group)
                    if isinstance(part_res, pd.Series):
                        pieces.append(part_res)
                    elif hasattr(part_res, "__iter__") and not isinstance(part_res, (str, bytes)):
                        pieces.append(pd.Series(list(part_res), index=group.index))
                    else:
                        pieces.append(pd.Series([part_res] * len(group), index=group.index))
                import pandas as pd

                full_col = pd.concat(pieces).reindex(pdf.index)
                new_map = dict(res._orig_col_map)
                new_map[col_name] = col_name
                res = DataFrame(
                    res._df.with_columns(pl.Series(col_name, full_col.to_numpy())), orig_col_map=new_map
                )
                res._orig_index = self._orig_index

        return res

    def agg(self, *specs: Any, a: Any = None, dropna: bool = False, **kwargs: Any) -> DataFrame:
        """Aggregate numeric columns or compute metrics grouped by the established keys."""
        if "by" in kwargs or "_by" in kwargs:
            raise TypeError(
                "df.pt.agg() does not accept 'by'. Set grouping beforehand using pt.by(df, 'col') or df.pt.by('col')."
            )
        return DataFrame(agg_polars(self._df, *specs, by=self._by, a=a, dropna=dropna, **kwargs))

    def dropna(self, *cols: Any, subset: Any = None, how: str | None = None, drop_nans: bool = True) -> DataFrame:
        """Drop rows containing missing values (Arrow null and/or float NaN)."""
        resolved = list(subset) if subset is not None else (list(cols) if cols else None)
        return DataFrame(dropna_polars(self._df, cols=resolved, how=how, drop_nans=drop_nans))

    def drop_nulls(self, *cols: Any, subset: Any = None, how: str | None = None, drop_nans: bool = True) -> DataFrame:
        """Alias for dropna()."""
        return self.dropna(*cols, subset=subset, how=how, drop_nans=drop_nans)

    def drop_na(self, *cols: Any, subset: Any = None, how: str | None = None, drop_nans: bool = True) -> DataFrame:
        """Alias for dropna()."""
        return self.dropna(*cols, subset=subset, how=how, drop_nans=drop_nans)

    def fillna(self, value: Any = None, *cols: Any, subset: Any = None, nans: bool = True) -> DataFrame:
        """Fill missing values (Arrow null and/or float NaN)."""
        if cols or subset is not None:
            target = list(subset) if subset is not None else list(cols)
            avail = set(self.columns)
            missing = [str(c) for c in target if str(c) not in avail]
            if missing:
                raise KeyError(f"fillna: column(s) {missing} not found in DataFrame")
        return DataFrame(fillna_polars(self._df, value, *cols, subset=subset, nans=nans))

    def fill_null(self, value: Any = None, *cols: Any, subset: Any = None) -> DataFrame:
        """Alias for fillna(..., nans=False) targeting Arrow nulls only."""
        return self.fillna(value, *cols, subset=subset, nans=False)

    def fill_nan(self, value: Any = None, *cols: Any, subset: Any = None) -> DataFrame:
        """Fill only float NaNs, leaving Arrow nulls unchanged."""
        if cols or subset is not None:
            target = list(subset) if subset is not None else list(cols)
            avail = set(self.columns)
            missing = [str(c) for c in target if str(c) not in avail]
            if missing:
                raise KeyError(f"fill_nan: column(s) {missing} not found in DataFrame")
        return DataFrame(fill_nan_polars(self._df, value, *cols, subset=subset))

    def cast(self, dtypes: Any = None, strict: bool = True, **kwargs: Any) -> DataFrame:
        """Cast column types using Polars native SIMD vectorization."""
        return DataFrame(cast_polars(self._df, dtypes=dtypes, strict=strict, **kwargs))

    def pick(
        self,
        spec: str,
        n: int | None = None,
        prop: float | None = None,
        order: str = "max",
        with_ties: bool = False,
        na_last: bool = True,
    ) -> DataFrame:
        """Select top/bottom rows per group."""
        return DataFrame(
            pick_polars(
                self._df,
                spec,
                by=self._by,
                n=n,
                prop=prop,
                order=order,
                with_ties=with_ties,
                na_last=na_last,
            )
        )

    def sample(
        self,
        n: int | None = None,
        frac: float | None = None,
        *,
        fraction: float | None = None,
        seed: int | None = None,
        random_state: int | None = None,
        with_replacement: bool = False,
        replace: bool = False,
        shuffle: bool = False,
    ) -> DataFrame:
        """Sample rows from each group established by pt.by()."""
        effective_frac = frac if frac is not None else fraction
        effective_seed = seed if seed is not None else random_state
        effective_replace = with_replacement or replace
        n_val = 5 if n is None and effective_frac is None else n

        eager_df = self._df.collect() if isinstance(self._df, pl.LazyFrame) else self._df
        parts = []
        for _, sub_df in eager_df.group_by(self._by):
            if effective_frac is not None:
                parts.append(
                    sub_df.sample(
                        fraction=effective_frac,
                        with_replacement=effective_replace,
                        shuffle=shuffle,
                        seed=effective_seed,
                    )
                )
            else:
                sample_n = min(n_val, len(sub_df)) if not effective_replace else n_val
                parts.append(
                    sub_df.sample(
                        n=sample_n,
                        with_replacement=effective_replace,
                        shuffle=shuffle,
                        seed=effective_seed,
                    )
                    if sample_n > 0
                    else sub_df.head(0)
                )
        res = pl.concat(parts) if parts else eager_df.head(0)
        return DataFrame(res, orig_col_map=self._orig_col_map)

    def __repr__(self) -> str:
        return f"<GroupedDataFrame by={self._by}>\n{self._df}"

    def _repr_html_(self) -> str:
        return f"<p><strong>Grouped by:</strong> {', '.join(self._by)}</p>{self._df._repr_html_()}"


def _plot_impl(pdf: Any, *args: Any, **kwargs: Any) -> Any:
    """Shared Plotter bridge implementation handling faceting and kwargs splitting."""
    try:
        from pytae.plotting import Plotter
    except ImportError as exc:
        raise ImportError("plot() requires matplotlib. Install with: pip install 'pytae[plot]'") from exc

    import pandas as pd

    if not isinstance(pdf, pd.DataFrame):
        if hasattr(pdf, "to_pandas"):
            pdf = pdf.to_pandas()
        else:
            pdf = pd.DataFrame(pdf)

    by_col = kwargs.get("by") if kwargs.get("by") is not None else kwargs.get("col")
    has_facet_trigger = kwargs.get("ncols") is not None or kwargs.get("facet") is True or "col" in kwargs
    is_plot_call = bool({"kind", "x", "y", "column"}.intersection(kwargs.keys()))

    if by_col is not None and by_col in pdf.columns and has_facet_trigger and is_plot_call:
        if "mosaic" in kwargs or (len(args) > 0 and args[0] is not None):
            raise ValueError("Cannot combine 'mosaic' with faceting ('by' with 'ncols'/'facet'/'col').")
        if "nrows" in kwargs:
            raise ValueError(
                "Cannot combine 'nrows' with faceting ('by' with 'ncols'/'facet'/'col'). Use 'ncols' to control grid columns."
            )

        facet_kwargs = dict(kwargs)
        facet_kwargs.pop("by", None)
        facet_kwargs.pop("col", None)
        facet_kwargs.pop("facet", None)
        ncols = facet_kwargs.pop("ncols", None)
        return Plotter.facet(pdf, by=by_col, ncols=ncols, **facet_kwargs)

    save_path = kwargs.pop("save", None)
    plotter_keys = {"mosaic", "figsize", "aggregate", "sharex", "sharey", "nrows", "ncols"}
    init_kwargs = {k: v for k, v in kwargs.items() if k in plotter_keys}
    plot_kwargs = {k: v for k, v in kwargs.items() if k not in plotter_keys}

    plotter = Plotter(*args, **init_kwargs)
    plotter.data(pdf)
    if plot_kwargs:
        plotter.plot(**plot_kwargs)
    if save_path:
        plotter.finalize().save(save_path)
    return plotter


# -----------------------------------------------------------------------------
# Pandas Testing Interop Hook
# -----------------------------------------------------------------------------
try:
    import pandas as pd
    import pandas._testing.asserters as _asserters

    _orig_assert_frame_equal = _asserters.assert_frame_equal

    def _pt_assert_frame_equal(left: Any, right: Any, *args: Any, **kwargs: Any) -> Any:
        if hasattr(left, "to_pandas"):
            left = left.to_pandas()
        if hasattr(right, "to_pandas"):
            right = right.to_pandas()
        return _orig_assert_frame_equal(left, right, *args, **kwargs)

    _asserters.assert_frame_equal = _pt_assert_frame_equal
    import pandas.testing as _pd_testing

    _pd_testing.assert_frame_equal = _pt_assert_frame_equal

    _orig_pd_melt = getattr(pd, "melt", None)
    if _orig_pd_melt is not None:

        def _compat_pd_melt(frame: Any, *args: Any, **kwargs: Any) -> Any:
            if hasattr(frame, "to_pandas") and not isinstance(frame, pd.DataFrame):
                frame = frame.to_pandas()
            return _orig_pd_melt(frame, *args, **kwargs)

        pd.melt = _compat_pd_melt
        import pandas.core.reshape.melt as _prm

        _prm.melt = _compat_pd_melt
except Exception:
    pass
