"""pytae: package functions (`pt.select(df, ...)`) and DataFrame accessor `df.pt`, plus a CLI."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from .accessor import PtAccessor  # noqa: F401  — registers df.pt
from .agg_df import agg_df
from .mutate import mutate
from .other_utilities import (
    clean_columns,
    cols,
    group_x,
    handle_missing,
    replace_values,
    snip,
)
from .qry import qry
from .select import everything, select
from .sql import sql

DATA_PATH = Path(__file__).resolve().parent / "datasets"
_DATASET_NAMES = tuple(sorted(p.stem for p in DATA_PATH.glob("*.parquet")))
_cache: dict[str, pd.DataFrame] = {}


def sample(name: str) -> pd.DataFrame:
    """Load a bundled sample dataset by name (cached after the first call).
    Returns a copy each time — mutating the result does not affect later calls."""
    if name not in _DATASET_NAMES:
        available = ", ".join(_DATASET_NAMES) or "(none)"
        raise KeyError(f"unknown dataset {name!r}; available: {available}")
    if name not in _cache:
        _cache[name] = pd.read_parquet(DATA_PATH / f"{name}.parquet")
    return _cache[name].copy()


class _SampleData(Mapping):
    """Bundled datasets, loaded from parquet on first access."""

    def __getitem__(self, name):
        return sample(name)

    def __contains__(self, name):
        return name in _DATASET_NAMES

    def __iter__(self):
        return iter(_DATASET_NAMES)

    def __len__(self):
        return len(_DATASET_NAMES)

    def keys(self):
        """Dataset names as a plain tuple (not a KeysView) so it's printable/readable
        directly, e.g. print(pytae.sample_data.keys())."""
        return _DATASET_NAMES


sample_data = _SampleData()


def _bind_shape():
    from .shape import long, wide
    globals()["long"] = long
    globals()["wide"] = wide
    return long, wide


def __getattr__(name):
    if name == "Plotter":
        try:
            from .plotting import Plotter
        except ImportError as exc:
            raise ImportError(
                "Plotter requires matplotlib. Install with: pip install 'pytae[plot]'"
            ) from exc
        return Plotter
    if name in ("long", "wide"):
        _bind_shape()
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "sample_data",
    "sample",
    "Plotter",
    "select",
    "qry",
    "mutate",
    "agg_df",
    "long",
    "wide",
    "group_x",
    "handle_missing",
    "cols",
    "snip",
    "clean_columns",
    "replace_values",
    "sql",
    "everything",
    "PtAccessor",
]
