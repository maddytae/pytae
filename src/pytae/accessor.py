"""DataFrame accessor `df.pt` registered on both Polars and Pandas DataFrames.

Allows entering Pytae's fluent grammar directly:
    df.pt.filter("amount > 0").by("region").mutate(prev="shift(amount, 1)").arrange("amount desc")
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import pandas as pd
import polars as pl

from pytae.dataframe import DataFrame, GroupedDataFrame, _plot_impl


@pl.api.register_dataframe_namespace("pt")
@pl.api.register_lazyframe_namespace("pt")
class PolarsPtAccessor:
    """Polars DataFrame and LazyFrame accessor entering Pytae's fluent data manipulation pipeline."""

    def __init__(self, obj: pl.DataFrame | pl.LazyFrame):
        self._obj = obj

    def filter(self, *conditions: Any, **kwargs: Any) -> DataFrame:
        return DataFrame(self._obj).filter(*conditions, **kwargs)

    def select(self, *names: Any, **kwargs: Any) -> DataFrame:
        return DataFrame(self._obj).select(*names, **kwargs)

    def arrange(self, *specs: str, na_last: bool = True) -> DataFrame:
        return DataFrame(self._obj).arrange(*specs, na_last=na_last)

    def distinct(self, *cols: Any, keep: str = "first") -> DataFrame:
        return DataFrame(self._obj).distinct(*cols, keep=keep)

    def count(self, *cols: Any, sort: bool = True, name: str = "n") -> DataFrame:
        return DataFrame(self._obj).count(*cols, sort=sort, name=name)

    def dropna(self, *cols: Any, subset: Any = None, how: str | None = None, drop_nans: bool = True) -> DataFrame:
        return DataFrame(self._obj).dropna(*cols, subset=subset, how=how, drop_nans=drop_nans)

    def fillna(self, value: Any = None, *cols: Any, subset: Any = None, nans: bool = True, **kwargs: Any) -> DataFrame:
        return DataFrame(self._obj).fillna(value, *cols, subset=subset, nans=nans, **kwargs)

    def diff(self, other: Any, tol: float = 0.0, rtol: float = 0.0) -> str:
        return DataFrame(self._obj).diff(other, tol=tol, rtol=rtol)

    def head(
        self,
        n: int | str | None = None,
        *,
        prop: float | None = None,
        with_ties: bool = False,
    ) -> DataFrame:
        return DataFrame(self._obj).head(n=n, prop=prop, with_ties=with_ties)

    def tail(
        self,
        n: int | str | None = None,
        *,
        prop: float | None = None,
        with_ties: bool = False,
    ) -> DataFrame:
        return DataFrame(self._obj).tail(n=n, prop=prop, with_ties=with_ties)

    def pick(self, *args: Any, **kwargs: Any) -> Any:
        raise AttributeError("df.pt.pick() has been removed; use df.pt.arrange(...).head(n) instead (or df.pt.by(...).arrange(...).head(n) for grouped slicing).")

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
        return DataFrame(self._obj).sample(
            n=n,
            frac=frac,
            fraction=fraction,
            seed=seed,
            random_state=random_state,
            with_replacement=with_replacement,
            replace=replace,
            shuffle=shuffle,
        )

    def by(self, *cols: Any) -> GroupedDataFrame:
        return DataFrame(self._obj).by(*cols)

    def mutate(self, *specs: Any, **kwargs: Any) -> DataFrame:
        return DataFrame(self._obj).mutate(*specs, **kwargs)

    def rename(self, *args: Any, columns: dict[str, str] | None = None, **kwargs: Any) -> DataFrame:
        return DataFrame(self._obj).rename(*args, columns=columns, **kwargs)

    def sql(self, query: str) -> DataFrame:
        return DataFrame(self._obj).sql(query)

    def agg(self, *specs: Any, a: Any = None, dropna: bool = False, **kwargs: Any) -> DataFrame:
        return DataFrame(self._obj).agg(*specs, a=a, dropna=dropna, **kwargs)

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
        return DataFrame(self._obj).pivot(r=r, c=c, v=v, a=a, dropna=dropna, f_v=f_v, **kwargs)

    def long(
        self,
        cols: str | Sequence[str] | None = None,
        id_vars: str | Sequence[str] | None = None,
        c: str = "variable",
        v: str = "value",
    ) -> DataFrame:
        return DataFrame(self._obj).long(cols=cols, id_vars=id_vars, c=c, v=v)

    def wide(
        self,
        r: str | Sequence[str] | None = None,
        c: str = "variable",
        v: str = "value",
        **kwargs: Any,
    ) -> DataFrame:
        return DataFrame(self._obj).wide(r=r, c=c, v=v, **kwargs)

    def clean_columns(self, **opts: Any) -> DataFrame:
        return DataFrame(self._obj).clean_columns(**opts)

    def cols(self, ascending: bool | None = True) -> list[str]:
        return DataFrame(self._obj).cols(ascending=ascending)

    def glimpse(self, width: int | None = None) -> pl.DataFrame:
        from pytae.other_utilities import format_glimpse

        print(format_glimpse(self._obj, width=width))
        return self._obj

    def freq(self, col: str | None = None, dropna: bool = False) -> DataFrame:
        return DataFrame(self._obj).freq(col=col, dropna=dropna)

    def hist(self, col: str | None = None, bins: int = 10) -> DataFrame:
        return DataFrame(self._obj).hist(col=col, bins=bins)

    def pipe(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return DataFrame(self._obj).pipe(func, *args, **kwargs)

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
        return DataFrame(self._obj).join(
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

    def concat(
        self,
        *others: Any,
        how: str = "vertical",
        axis: int | str | None = None,
        **kwargs: Any,
    ) -> DataFrame:
        return DataFrame(self._obj).concat(*others, how=how, axis=axis, **kwargs)

    def to_clip(self) -> None:
        return DataFrame(self._obj).to_clip()

    def to_pandas(self) -> Any:
        return DataFrame(self._obj).to_pandas()

    def to_polars(self) -> pl.DataFrame | pl.LazyFrame:
        return self._obj

    def plot(self, *args: Any, **kwargs: Any) -> Any:
        return _plot_impl(self._obj, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(DataFrame(self._obj), name)


@pd.api.extensions.register_dataframe_accessor("pt")
class PandasPtAccessor:
    """Pandas DataFrame accessor providing a seamless zero-friction bridge into Pytae's Polars engine."""

    def __init__(self, obj: pd.DataFrame):
        self._obj = obj

    def filter(self, *conditions: Any, **kwargs: Any) -> DataFrame:
        return DataFrame(self._obj).filter(*conditions, **kwargs)

    def select(self, *names: Any, **kwargs: Any) -> DataFrame:
        return DataFrame(self._obj).select(*names, **kwargs)

    def arrange(self, *specs: str, na_last: bool = True) -> DataFrame:
        return DataFrame(self._obj).arrange(*specs, na_last=na_last)

    def distinct(self, *cols: Any, keep: str = "first") -> DataFrame:
        return DataFrame(self._obj).distinct(*cols, keep=keep)

    def count(self, *cols: Any, sort: bool = True, name: str = "n") -> DataFrame:
        return DataFrame(self._obj).count(*cols, sort=sort, name=name)

    def dropna(self, *cols: Any, subset: Any = None, how: str | None = None, drop_nans: bool = True) -> DataFrame:
        return DataFrame(self._obj).dropna(*cols, subset=subset, how=how, drop_nans=drop_nans)

    def fillna(self, value: Any = None, *cols: Any, subset: Any = None, nans: bool = True, **kwargs: Any) -> DataFrame:
        return DataFrame(self._obj).fillna(value, *cols, subset=subset, nans=nans, **kwargs)

    def diff(self, other: Any, tol: float = 0.0, rtol: float = 0.0) -> str:
        return DataFrame(self._obj).diff(other, tol=tol, rtol=rtol)

    def head(
        self,
        n: int | str | None = None,
        *,
        prop: float | None = None,
        with_ties: bool = False,
    ) -> DataFrame:
        return DataFrame(self._obj).head(n=n, prop=prop, with_ties=with_ties)

    def tail(
        self,
        n: int | str | None = None,
        *,
        prop: float | None = None,
        with_ties: bool = False,
    ) -> DataFrame:
        return DataFrame(self._obj).tail(n=n, prop=prop, with_ties=with_ties)

    def pick(self, *args: Any, **kwargs: Any) -> Any:
        raise AttributeError("df.pt.pick() has been removed; use df.pt.arrange(...).head(n) instead (or df.pt.by(...).arrange(...).head(n) for grouped slicing).")

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
        return DataFrame(self._obj).sample(
            n=n,
            frac=frac,
            fraction=fraction,
            seed=seed,
            random_state=random_state,
            with_replacement=with_replacement,
            replace=replace,
            shuffle=shuffle,
        )

    def by(self, *cols: Any) -> GroupedDataFrame:
        return DataFrame(self._obj).by(*cols)

    def mutate(self, *specs: Any, **kwargs: Any) -> DataFrame:
        return DataFrame(self._obj).mutate(*specs, **kwargs)

    def rename(self, *args: Any, columns: dict[str, str] | None = None, **kwargs: Any) -> DataFrame:
        return DataFrame(self._obj).rename(*args, columns=columns, **kwargs)

    def sql(self, query: str) -> DataFrame:
        return DataFrame(self._obj).sql(query)

    def agg(self, *specs: Any, a: Any = None, dropna: bool = False, **kwargs: Any) -> DataFrame:
        if "by" in kwargs or "_by" in kwargs:
            raise TypeError(
                "df.pt.agg() does not accept 'by'. Set grouping beforehand using pt.by(df, 'col') or df.pt.by('col')."
            )
        return DataFrame(self._obj).agg(*specs, a=a, dropna=dropna, **kwargs)

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
        return DataFrame(self._obj).pivot(r=r, c=c, v=v, a=a, dropna=dropna, f_v=f_v, **kwargs)

    def long(
        self,
        cols: str | Sequence[str] | None = None,
        id_vars: str | Sequence[str] | None = None,
        c: str = "variable",
        v: str = "value",
    ) -> DataFrame:
        return DataFrame(self._obj).long(cols=cols, id_vars=id_vars, c=c, v=v)

    def wide(
        self,
        r: str | Sequence[str] | None = None,
        c: str = "variable",
        v: str = "value",
        **kwargs: Any,
    ) -> DataFrame:
        return DataFrame(self._obj).wide(r=r, c=c, v=v, **kwargs)

    def clean_columns(self, **opts: Any) -> DataFrame:
        return DataFrame(self._obj).clean_columns(**opts)

    def cols(self, ascending: bool | None = True) -> list[str]:
        return DataFrame(self._obj).cols(ascending=ascending)

    def glimpse(self, width: int | None = None) -> pd.DataFrame:
        from pytae.other_utilities import format_glimpse

        print(format_glimpse(self._obj, width=width))
        return self._obj

    def freq(self, col: str | None = None, dropna: bool = False) -> DataFrame:
        return DataFrame(self._obj).freq(col=col, dropna=dropna)

    def hist(self, col: str | None = None, bins: int = 10) -> DataFrame:
        return DataFrame(self._obj).hist(col=col, bins=bins)

    def pipe(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return DataFrame(self._obj).pipe(func, *args, **kwargs)

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
        return DataFrame(self._obj).join(
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

    def concat(
        self,
        *others: Any,
        how: str = "vertical",
        axis: int | str | None = None,
        **kwargs: Any,
    ) -> DataFrame:
        return DataFrame(self._obj).concat(*others, how=how, axis=axis, **kwargs)

    def to_clip(self) -> None:
        return self._obj.to_clipboard(index=False)

    def safe_reset_index(self) -> pd.DataFrame:
        from pytae.other_utilities import safe_reset_index

        return safe_reset_index(self._obj)

    def to_pandas(self) -> pd.DataFrame:
        return self._obj

    def to_polars(self) -> pl.DataFrame:
        return DataFrame(self._obj).to_polars()

    def plot(self, *args: Any, **kwargs: Any) -> Any:
        return _plot_impl(self._obj, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(DataFrame(self._obj), name)
