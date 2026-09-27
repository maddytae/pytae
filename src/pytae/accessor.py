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
    def __init__(self, pandas_obj: pd.DataFrame):
        self._obj = pandas_obj

    def select(self, *args: Any, **kwargs: Any) -> pd.DataFrame:
        return _select(self._obj, *args, **kwargs)

    def qry(self, *args: Any, **kwargs: Any) -> pd.DataFrame:
        return _qry(self._obj, *args, **kwargs)

    def mutate(
        self,
        *args: Any,
        by: str | Sequence[str] | None = None,
        dropna: bool = True,
        observed: bool = True,
        **kwargs: Any,
    ) -> pd.DataFrame:
        return _mutate(self._obj, *args, by=by, dropna=dropna, observed=observed, **kwargs)

    def sql(self, query: str, /, **frames: pd.DataFrame) -> pd.DataFrame:
        return _sql(self._obj, query, **frames)

    def agg_df(
        self,
        by: str | Sequence[str] | None = _UNSET,  # type: ignore[assignment]
        *args: Any,
        **kwargs: Any,
    ) -> pd.DataFrame:
        return _agg_df(self._obj, by, *args, **kwargs)

    def agg(
        self,
        by: str | Sequence[str] | None = _UNSET,  # type: ignore[assignment]
        *args: Any,
        **kwargs: Any,
    ) -> pd.DataFrame:
        return _agg_df(self._obj, by, *args, **kwargs)

    def long(
        self,
        cols: str | Sequence[str] | None = None,
        id_vars: str | Sequence[str] | None = None,
        c: str = "variable",
        v: str = "value",
        **kwargs: Any,
    ) -> pd.DataFrame:
        from .shape import long as _long
        return _long(self._obj, cols=cols, id_vars=id_vars, c=c, v=v, **kwargs)

    def wide(
        self,
        c: str = "variable",
        v: str = "value",
        a: str | None = None,
        dropna: bool = True,
        index: str | Sequence[str] | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        from .shape import wide as _wide
        return _wide(self._obj, c=c, v=v, a=a, dropna=dropna, index=index, **kwargs)

    def handle_missing(
        self,
        fillna: str = ".",
        numeric_fill: Any = 0,
        cols: Sequence[str] | None = None,
        preserve_categories: bool = True,
    ) -> pd.DataFrame:
        return _handle_missing(
            self._obj,
            fillna=fillna,
            numeric_fill=numeric_fill,
            cols=cols,
            preserve_categories=preserve_categories,
        )

    def cols(self, ascending: bool | None = True) -> list:
        return _cols(self._obj, ascending=ascending)

    def clean_columns(self, **kwargs: Any) -> pd.DataFrame:
        return _clean_columns(self._obj, **kwargs)

    def replace_values(
        self, v: dict[Any, Any], c: str | Sequence[str] | None = None, exact: bool = True
    ) -> pd.DataFrame:
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

        by_col = kwargs.get("by") or kwargs.get("col")
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
            and by_col
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

        plotter_keys = {"mosaic", "figsize", "aggregate", "sharex", "sharey", "nrows", "ncols"}
        init_kwargs = {k: v for k, v in kwargs.items() if k in plotter_keys}
        plot_kwargs = {k: v for k, v in kwargs.items() if k not in plotter_keys}

        plotter = Plotter(*args, **init_kwargs)
        plotter.data(self._obj)
        if plot_kwargs:
            plotter.plot(**plot_kwargs)
        return plotter

