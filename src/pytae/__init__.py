"""pytae: Supercharged CLI and library tabular data manipulation tool.

A modern, fluent, Polars-backed tabular data wrangling grammar for Python.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from pytae._parsing import lit
from pytae.accessor import PandasPtAccessor, PolarsPtAccessor
from pytae.dataframe import DataFrame, GroupedDataFrame
from pytae.other_utilities import format_glimpse
from pytae.readers import read, scan
from pytae.select import everything

__version__ = "3.10.0"

DATA_PATH = Path(__file__).resolve().parent / "datasets"
_DATASET_NAMES = tuple(sorted(p.stem for p in DATA_PATH.glob("*.parquet")))
_cache: dict[str, DataFrame] = {}


def sample(name: str = "penguins") -> DataFrame:
    """Load a bundled sample dataset by name (cached after the first call).
    Returns a copy each time — mutating the result does not affect later calls."""
    if name not in _DATASET_NAMES:
        available = ", ".join(_DATASET_NAMES) or "(none)"
        raise KeyError(f"unknown dataset {name!r}; available: {available}")
    if name not in _cache:
        _cache[name] = read(DATA_PATH / f"{name}.parquet")
    return _cache[name].copy()


class _SampleData(Mapping[str, DataFrame]):
    """Bundled datasets, loaded from parquet on first access."""

    def __call__(self, name: str = "penguins") -> DataFrame:
        return sample(name)

    def __getitem__(self, name: str) -> DataFrame:
        return sample(name)

    def __contains__(self, name: object) -> bool:
        return name in _DATASET_NAMES

    def __iter__(self):
        return iter(_DATASET_NAMES)

    def __len__(self) -> int:
        return len(_DATASET_NAMES)

    def keys(self) -> tuple[str, ...]:
        """Dataset names as a plain tuple (not a KeysView) so it's printable/readable
        directly, e.g. print(pytae.sample_data.keys())."""
        return _DATASET_NAMES


sample_data = _SampleData()


# -----------------------------------------------------------------------------
# Functional API (accepts Pytae DataFrame, Polars DataFrame, or Pandas DataFrame)
# -----------------------------------------------------------------------------


def select(df: Any, *args: Any, **kwargs: Any) -> DataFrame:
    return DataFrame(df).select(*args, **kwargs)


def filter(df: Any, *conditions: Any, **kwargs: Any) -> DataFrame:
    return DataFrame(df).filter(*conditions, **kwargs)


def mutate(df: Any, *specs: Any, **kwargs: Any) -> DataFrame:
    if isinstance(df, GroupedDataFrame):
        return df.mutate(*specs, **kwargs)
    return DataFrame(df).mutate(*specs, **kwargs)


def arrange(df: Any, *specs: str, na_last: bool = True) -> DataFrame:
    return DataFrame(df).arrange(*specs, na_last=na_last)


def pick(df: Any, spec: str, n: int | None = None, **kwargs: Any) -> DataFrame:
    if isinstance(df, GroupedDataFrame):
        return df.pick(spec, n=n, **kwargs)
    return DataFrame(df).pick(spec, n=n, **kwargs)


def distinct(df: Any, *cols: Any, keep: str = "first") -> DataFrame:
    return DataFrame(df).distinct(*cols, keep=keep)


def dropna(df: Any, *cols: Any) -> DataFrame:
    return DataFrame(df).dropna(*cols)


def by(df: Any, *cols: Any) -> GroupedDataFrame:
    return DataFrame(df).by(*cols)


def ungroup(df: Any) -> DataFrame:
    if isinstance(df, GroupedDataFrame):
        return df.ungroup()
    return DataFrame(df)


def agg(df: Any, *specs: Any, a: Any = None, dropna: bool = False, **kwargs: Any) -> DataFrame:
    if "by" in kwargs or "_by" in kwargs:
        raise TypeError(
            "agg() does not accept 'by'. Set grouping beforehand using pt.by(df, 'col') or df.pt.by('col')."
        )
    if isinstance(df, GroupedDataFrame):
        return df.agg(*specs, a=a, dropna=dropna, **kwargs)
    return DataFrame(df).agg(*specs, a=a, dropna=dropna, **kwargs)


def pivot(
    df: Any,
    r: str | Sequence[str] | None = None,
    c: str | Sequence[str] | None = None,
    v: str | Sequence[str] | None = None,
    a: str = "sum",
    dropna: bool = False,
    f_v: Any = None,
    **kwargs: Any,
) -> DataFrame:
    return DataFrame(df).pivot(r=r, c=c, v=v, a=a, dropna=dropna, f_v=f_v, **kwargs)


def long(
    df: Any,
    cols: str | Sequence[str] | None = None,
    id_vars: str | Sequence[str] | None = None,
    c: str = "variable",
    v: str = "value",
) -> DataFrame:
    return DataFrame(df).long(cols=cols, id_vars=id_vars, c=c, v=v)


def wide(
    df: Any,
    r: str | Sequence[str] | None = None,
    c: str = "variable",
    v: str = "value",
    **kwargs: Any,
) -> DataFrame:
    return DataFrame(df).wide(r=r, c=c, v=v, **kwargs)


def clean_columns(df: Any, **opts: Any) -> DataFrame:
    return DataFrame(df).clean_columns(**opts)


def replace_values(df: Any, v: dict[Any, Any], **kwargs: Any) -> DataFrame:
    return DataFrame(df).replace_values(v, **kwargs)


def handle_missing(df: Any, **opts: Any) -> DataFrame:
    return DataFrame(df).handle_missing(**opts)


def cols(df: Any, ascending: bool | None = True) -> list[str]:
    return DataFrame(df).cols(ascending=ascending)


def glimpse(df: Any, width: int | None = None) -> DataFrame:
    return DataFrame(df).glimpse(width=width)


def freq(df: Any, col: str | None = None, dropna: bool = False) -> DataFrame:
    return DataFrame(df).freq(col=col, dropna=dropna)


def hist(df: Any, col: str | None = None, bins: int = 10) -> DataFrame:
    return DataFrame(df).hist(col=col, bins=bins)


def slice_max(*args: Any, **kwargs: Any) -> None:
    raise AttributeError("pt.slice_max() has been removed; use pt.pick() instead")


def slice_min(*args: Any, **kwargs: Any) -> None:
    raise AttributeError("pt.slice_min() has been removed; use pt.pick(..., order='min') instead")


class _VerbDescriptor:
    def __init__(self, func: Any) -> None:
        self.func = func

    def __get__(self, instance: Any, owner: Any = None) -> Any:
        return self.func

    def __set__(self, instance: Any, value: Any) -> None:
        pass


# Make module callable as pt(data) -> DataFrame, and dispatch verbs via descriptors to prevent submodule shadowing
class _PytaeModule(ModuleType):
    def __call__(self, data: Any = None) -> DataFrame:
        return DataFrame(data)

    select = _VerbDescriptor(select)
    filter = _VerbDescriptor(filter)
    mutate = _VerbDescriptor(mutate)
    arrange = _VerbDescriptor(arrange)
    pick = _VerbDescriptor(pick)
    distinct = _VerbDescriptor(distinct)
    dropna = _VerbDescriptor(dropna)
    by = _VerbDescriptor(by)
    ungroup = _VerbDescriptor(ungroup)
    agg = _VerbDescriptor(agg)
    pivot = _VerbDescriptor(pivot)
    long = _VerbDescriptor(long)
    wide = _VerbDescriptor(wide)
    clean_columns = _VerbDescriptor(clean_columns)
    replace_values = _VerbDescriptor(replace_values)
    handle_missing = _VerbDescriptor(handle_missing)
    cols = _VerbDescriptor(cols)
    glimpse = _VerbDescriptor(glimpse)
    freq = _VerbDescriptor(freq)
    hist = _VerbDescriptor(hist)
    slice_max = _VerbDescriptor(slice_max)
    slice_min = _VerbDescriptor(slice_min)
    lit = _VerbDescriptor(lit)
    sample = _VerbDescriptor(sample)
    sample_data = _VerbDescriptor(sample_data)
    scan = _VerbDescriptor(scan)


sys.modules[__name__].__class__ = _PytaeModule


def __getattr__(name: str) -> Any:
    if name in ("Plotter", "plot", "finalize"):
        try:
            from .plotting import Plotter, finalize, plot

            if name == "Plotter":
                return Plotter
            elif name == "plot":
                return plot
            else:
                return finalize
        except ImportError as exc:
            raise ImportError(f"{name} requires matplotlib. Install with: pip install 'pytae[plot]'") from exc
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DataFrame",
    "GroupedDataFrame",
    "read",
    "scan",
    "sample_data",
    "sample",
    "select",
    "filter",
    "by",
    "ungroup",
    "mutate",
    "arrange",
    "pick",
    "distinct",
    "dropna",
    "agg",
    "long",
    "wide",
    "pivot",
    "handle_missing",
    "cols",
    "freq",
    "glimpse",
    "format_glimpse",
    "hist",
    "clean_columns",
    "replace_values",
    "lit",
    "everything",
    "PolarsPtAccessor",
    "PandasPtAccessor",
]
