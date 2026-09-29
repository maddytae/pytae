"""DataFrame accessor `df.pt` — mix with pandas methods in one chain.

    df.rename(columns={...}).pt.agg_df(a="mean")
    df.pt.select("species", contains="bill").head()
    df.pt.select("species", "body_mass_g").pt.agg_df(a=["mean", "n"])
    df.pt.sql("select species, avg(body_mass_g) from data group by species")
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd

from .agg_df import _UNSET
from .agg_df import agg_df as _agg_df
from .mutate import mutate as _mutate
from .other_utilities import (
    clean_columns as _clean_columns,
)
from .other_utilities import (
    cols as _cols,
)
from .other_utilities import (
    handle_missing as _handle_missing,
)
from .other_utilities import (
    replace_values as _replace_values,
)
from .qry import qry as _qry
from .select import select as _select
from .sql import sql as _sql


@pd.api.extensions.register_dataframe_accessor("pt")
class PtAccessor:
    """Pandas DataFrame accessor (`df.pt`) providing ergonomic tabular verbs:
    - select: Column selection, slicing, negative exclusion, and type filtering.
    - qry: Row filtering via string expressions, dicts, intervals, and kwargs.
    - mutate: Feature engineering, formulas, and grouped transforms (`by=`).
    - agg_df / agg: Grouped aggregations (`by=`) and whole-table summaries (`by=None`).
    - long / wide: Reshaping (melting to rows and pivoting to columns).
    - sql: DuckDB SQL queries over the DataFrame (as table `data`).
    - clean_columns: Standardizing and normalizing column header names.
    - replace_values: Cell value replacement (exact or substring).
    - handle_missing: Missing value imputation with type-safe defaults.
    - cols: Column names sorted alphabetically or preserved in order.
    - plot: Method-chainable visualization engine with faceting and mosaics.
    """

    def __init__(self, pandas_obj: pd.DataFrame):
        self._obj = pandas_obj

    def select(self, *args: Any, **kwargs: Any) -> pd.DataFrame:
        """Select, reorder, or exclude columns by name, pattern, slice, or dtype.

        Supports exact names, negative prefixes ('-col', '~col'), negative slices
        ('-start:end'), regex, dtype filters ('dtype=numeric'), and 'exclude=' kwargs.
        """
        return _select(self._obj, *args, **kwargs)

    def qry(self, *args: Any, **kwargs: Any) -> pd.DataFrame:
        """Filter rows using human-readable conditions, dicts, or kwargs.

        Supports comparisons ('>', '<=', '=='), intervals ('[min, max]'), set
        membership (['a', 'b']), string operations ('startswith', 'contains'),
        and safe handling of column names with spaces.
        """
        return _qry(self._obj, *args, **kwargs)

    def mutate(
        self,
        *args: Any,
        by: str | Sequence[str] | None = None,
        dropna: bool = False,
        observed: bool = True,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Create or overwrite columns using formulas, callables, or grouped window transforms.

        Expressions evaluate sequentially via pandas eval() with automatic fallback.
        When `by=` is given, aggregations (mean, sum, n, etc.) evaluate per group and broadcast
        back to each row without collapsing the dataset.
        """
        return _mutate(self._obj, *args, by=by, dropna=dropna, observed=observed, **kwargs)

    def sql(self, query: str, /, **frames: pd.DataFrame) -> pd.DataFrame:
        """Run DuckDB SQL queries over this DataFrame (registered as table `data`).

        Additional DataFrames can be registered as keyword arguments. Spaced column
        names can use brackets `[col]`, double quotes `"col"`, or backticks.
        """
        return _sql(self._obj, query, **frames)

    def agg_df(
        self,
        by: str | Sequence[str] | None = _UNSET,  # type: ignore[assignment]
        *args: Any,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Aggregate numeric columns grouped by explicit `by` column(s).

        Pass `by=None` for a whole-table summary (1 row). Supports whole-frame
        functions ('mean', ['mean', 'n']), column mapping strings with brackets
        ('tip = mean, [total bill] = mean, n = n'), and keyword arguments.
        """
        return _agg_df(self._obj, by, *args, **kwargs)

    def agg(
        self,
        by: str | Sequence[str] | None = _UNSET,  # type: ignore[assignment]
        *args: Any,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Alias for `df.pt.agg_df()`: aggregate numeric columns grouped by `by` column(s)."""
        return _agg_df(self._obj, by, *args, **kwargs)

    def long(
        self,
        cols: str | Sequence[str] | None = None,
        id_vars: str | Sequence[str] | None = None,
        c: str = "variable",
        v: str = "value",
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Melt columns to rows (unpivot wide format into long format).

        Default melts all numeric columns, storing variable names in `c` (default 'variable')
        and values in `v` (default 'value').
        """
        from .shape import long as _long
        return _long(self._obj, cols=cols, id_vars=id_vars, c=c, v=v, **kwargs)

    def wide(
        self,
        c: str = "variable",
        v: str = "value",
        index: str | Sequence[str] | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Pivot long-form records back to wide format (columns).

        Headers are created from `c` (default 'variable'), cells from `v` (default 'value').
        Strictly 1-to-1 structural reshaping without aggregation.
        For multi-dimensional aggregation, use `df.pt.pivot()`.
        """
        from .shape import wide as _wide
        return _wide(self._obj, c=c, v=v, index=index, **kwargs)

    def pivot(
        self,
        r: str | Sequence[str] | None = None,
        c: str | Sequence[str] | None = None,
        v: str | Sequence[str] | None = None,
        a: str = "sum",
        dropna: bool = False,
        fill_value: Any = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Summarize and aggregate DataFrame across dimensions (Excel-style pivot table).

        Parameters:
        -----------
        r : str or sequence of str, optional
            Row dimension(s) to group by. Aliases: `rows`, `row`, `index`, `by`.
        c : str or sequence of str, optional
            Column dimension(s) to spread as headers. Aliases: `cols`, `col`, `columns`.
        v : str or sequence of str
            Value column(s) to aggregate. REQUIRED. Aliases: `values`, `value`, `val`, `vals`.
        a : str, default 'sum'
            Aggregation function ('sum', 'mean', 'median', 'min', 'max', 'count', 'std', etc.).
            'n' is accepted as an alias for 'size' (group row count). Aliases: `agg`, `aggfunc`.
        dropna : bool, default False
            Whether to drop NA categories from grouping keys.
        fill_value : any, optional
            Value to replace missing grid intersections with (e.g. 0).

        Returns:
        --------
        pd.DataFrame
            Clean, flattened DataFrame with standard RangeIndex and 1D column names.
        """
        from .shape import pivot as _pivot
        return _pivot(self._obj, r=r, c=c, v=v, a=a, dropna=dropna, fill_value=fill_value, **kwargs)

    def handle_missing(
        self,
        fillna: str = ".",
        numeric_fill: Any = 0,
        cols: Sequence[str] | None = None,
        preserve_categories: bool = True,
    ) -> pd.DataFrame:
        """Fill missing values with type-appropriate defaults across columns."""
        return _handle_missing(
            self._obj,
            fillna=fillna,
            numeric_fill=numeric_fill,
            cols=cols,
            preserve_categories=preserve_categories,
        )

    def cols(self, ascending: bool | None = True) -> list:
        """Return the column names sorted alphabetically (True/False) or in original order (None)."""
        return _cols(self._obj, ascending=ascending)

    def clean_columns(self, **kwargs: Any) -> pd.DataFrame:
        """Clean and standardize column header names (strip, squeeze, fill, case, dedupe)."""
        return _clean_columns(self._obj, **kwargs)

    def replace_values(
        self, v: dict[Any, Any], c: str | Sequence[str] | None = None, exact: bool = True
    ) -> pd.DataFrame:
        """Replace cell values via `{old: new}` mapping, optionally scoped to columns `c`."""
        return _replace_values(self._obj, v, c=c, exact=exact)

    def plot(self, *args: Any, **kwargs: Any) -> Any:
        """Create a pytae Plotter pre-loaded with this DataFrame.

        Can be called with layout parameters to start a pipeline:
            df.pt.plot(mosaic="AB", figsize=(10, 5)).plot(on="A", ...)

        Or with direct plot arguments to plot immediately:
            df.pt.plot(kind="bar", x="day", y="total_bill", aggfunc="mean").pt.finalize()

        Or with faceting parameters (e.g. by="species", ncols=3) to automatically
        produce a small-multiples grid across groups:
            df.pt.plot(by="species", ncols=3, kind="scatter", x="a", y="b").pt.finalize()
        """
        try:
            from .plotting import Plotter
        except ImportError as exc:
            raise ImportError(
                "df.pt.plot() requires matplotlib. Install with: pip install 'pytae[plot]'"
            ) from exc

        by_col = kwargs.get("by") if kwargs.get("by") is not None else kwargs.get("col")
        has_facet_trigger = (
            kwargs.get("ncols") is not None
            or kwargs.get("facet") is True
            or "col" in kwargs
        )
        is_plot_call = bool(
            {"kind", "x", "y", "column"}.intersection(kwargs.keys())
        )

        if (
            isinstance(self._obj, pd.DataFrame)
            and by_col is not None
            and by_col in self._obj
            and has_facet_trigger
            and is_plot_call
        ):
            if "mosaic" in kwargs or (len(args) > 0 and args[0] is not None):
                raise ValueError("Cannot combine 'mosaic' with faceting ('by' with 'ncols'/'facet'/'col').")
            if "nrows" in kwargs:
                raise ValueError("Cannot combine 'nrows' with faceting ('by' with 'ncols'/'facet'/'col'). Use 'ncols' to control grid columns.")

            facet_kwargs = dict(kwargs)
            facet_kwargs.pop("by", None)
            facet_kwargs.pop("col", None)
            facet_kwargs.pop("facet", None)
            ncols = facet_kwargs.pop("ncols", None)
            return Plotter.facet(self._obj, by=by_col, ncols=ncols, **facet_kwargs)

        save_path = kwargs.pop("save", None)
        plotter_keys = {"mosaic", "figsize", "aggregate", "sharex", "sharey", "nrows", "ncols"}
        init_kwargs = {k: v for k, v in kwargs.items() if k in plotter_keys}
        plot_kwargs = {k: v for k, v in kwargs.items() if k not in plotter_keys}

        plotter = Plotter(*args, **init_kwargs)
        plotter.data(self._obj)
        if plot_kwargs:
            plotter.plot(**plot_kwargs)
        if save_path:
            plotter.finalize().save(save_path)
        return plotter

