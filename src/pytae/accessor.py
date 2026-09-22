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

from .agg_df import agg_df as _agg_df
from .mutate import mutate as _mutate
from .other_utilities import (
    clean_columns as _clean_columns,
)
from .other_utilities import (
    cols as _cols,
)
from .other_utilities import (
    group_x as _group_x,
)
from .other_utilities import (
    handle_missing as _handle_missing,
)
from .other_utilities import (
    replace_values as _replace_values,
)
from .other_utilities import (
    to_clip as _to_clip,
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

    def qry(self, conditions: dict[str, Any] | str | None = None, **kwargs: Any) -> pd.DataFrame:
        return _qry(self._obj, conditions, **kwargs)

    def mutate(self, spec: str | dict[str, Any] | None = None, **kwargs: Any) -> pd.DataFrame:
        return _mutate(self._obj, spec, **kwargs)

    def sql(self, query: str, /, **frames: pd.DataFrame) -> pd.DataFrame:
        return _sql(self._obj, query, **frames)

    def agg_df(self, *args: Any, **kwargs: Any) -> pd.DataFrame:
        return _agg_df(self._obj, *args, **kwargs)

    def long(self, c: str = "variable", v: str = "value") -> pd.DataFrame:
        from .shape import long as _long
        return _long(self._obj, c=c, v=v)

    def wide(
        self, c: str = "variable", v: str = "value", a: str | None = None, dropna: bool = True
    ) -> pd.DataFrame:
        from .shape import wide as _wide
        return _wide(self._obj, c=c, v=v, a=a, dropna=dropna)

    def group_x(
        self,
        group: str | Sequence[str] | None = None,
        dropna: bool = True,
        observed: bool = True,
        a: str = "n",
        v: str | None = None,
    ) -> pd.DataFrame:
        return _group_x(self._obj, group=group, dropna=dropna, observed=observed, a=a, v=v)

    def handle_missing(self, fillna: str = ".") -> pd.DataFrame:
        return _handle_missing(self._obj, fillna=fillna)

    def cols(self, ascending: bool | None = True) -> list:
        return _cols(self._obj, ascending=ascending)

    def to_clip(self) -> None:
        return _to_clip(self._obj)

    def clean_columns(self, **kwargs: Any) -> pd.DataFrame:
        return _clean_columns(self._obj, **kwargs)

    def replace_values(
        self, v: dict[Any, Any], c: str | Sequence[str] | None = None, exact: bool = True
    ) -> pd.DataFrame:
        return _replace_values(self._obj, v, c=c, exact=exact)
