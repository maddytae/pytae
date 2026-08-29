from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from .agg_df import *
from .other_utilities import *
from .qry import *
from .select import *
from .shape import *

DATA_PATH = Path(__file__).resolve().parent / "datasets"
_DATASET_NAMES = tuple(sorted(p.stem for p in DATA_PATH.glob("*.parquet")))
_cache = {}


def sample(name):
    """Load a bundled sample dataset by name (cached after the first call)."""
    if name not in _DATASET_NAMES:
        available = ", ".join(_DATASET_NAMES) or "(none)"
        raise KeyError(f"unknown dataset {name!r}; available: {available}")
    if name not in _cache:
        _cache[name] = pd.read_parquet(DATA_PATH / f"{name}.parquet")
    return _cache[name]


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


sample_data = _SampleData()


def __getattr__(name):
    if name == "Plotter":
        from .plotting import Plotter
        return Plotter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["sample_data", "sample", "Plotter"]
