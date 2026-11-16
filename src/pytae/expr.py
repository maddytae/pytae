"""Universal Column Expression System for Pytae (c. architecture).

Provides the first-class `c` column proxy and `ColumnExpr` objects for type-safe,
autocomplete-friendly, zero-string-overhead data transformations compiled directly
to Polars SIMD expressions.
"""

from __future__ import annotations

from typing import Any, Sequence

import polars as pl


class SortExpr:
    """Represents a column sorting specification (ascending or descending)."""

    def __init__(self, expr: ColumnExpr, descending: bool = False) -> None:
        self.column_expr = expr
        self.descending = descending

    @property
    def name(self) -> str | None:
        return self.column_expr.name

    def to_polars(self) -> tuple[pl.Expr, bool]:
        return (self.column_expr.to_polars(), self.descending)

    def __repr__(self) -> str:
        direction = "desc()" if self.descending else "asc()"
        return f"{self.column_expr}.{direction}"


class RangeExpr:
    """Represents a contiguous column range selection (e.g. c.start.to(c.end))."""

    def __init__(self, start: str | ColumnExpr, end: str | ColumnExpr) -> None:
        self.start = start.name if isinstance(start, ColumnExpr) else str(start)
        self.end = end.name if isinstance(end, ColumnExpr) else str(end)
        if not self.start or not self.end:
            raise ValueError("RangeExpr requires named start and end columns")

    def __invert__(self) -> ExclusionExpr:
        """Allow dropping a range with ~: e.g. ~c.id.to(c.salary)."""
        return ExclusionExpr(self)

    def resolve(self, all_columns: Sequence[str]) -> list[str]:
        """Resolve this range against the available table columns."""
        cols = list(all_columns)
        if self.start not in cols:
            raise KeyError(f"Start column '{self.start}' not found in table columns")
        if self.end not in cols:
            raise KeyError(f"End column '{self.end}' not found in table columns")
        start_idx = cols.index(self.start)
        end_idx = cols.index(self.end)
        if start_idx <= end_idx:
            return cols[start_idx : end_idx + 1]
        return cols[end_idx : start_idx + 1]

    def __repr__(self) -> str:
        return f"c.{self.start}.to(c.{self.end})"


class ExclusionExpr:
    """Represents a column or range exclusion (e.g. ~c.ssn or ~c.start.to(c.end))."""

    def __init__(self, target: ColumnExpr | RangeExpr | str) -> None:
        if isinstance(target, ColumnExpr):
            if not target.name:
                raise ValueError("Cannot exclude a non-named computed expression")
            self.target: str | RangeExpr = target.name
        elif isinstance(target, RangeExpr):
            self.target = target
        else:
            self.target = str(target)

    def resolve_exclusions(self, all_columns: Sequence[str]) -> list[str]:
        if isinstance(self.target, RangeExpr):
            return self.target.resolve(all_columns)
        if self.target not in all_columns:
            raise KeyError(f"Column to exclude not found: '{self.target}'")
        return [self.target]

    def __repr__(self) -> str:
        if isinstance(self.target, RangeExpr):
            return f"~{self.target}"
        return f"~c.{self.target}"


class FillExpr:
    """Represents a missing-value imputation expression (e.g. c.salary.fill(0))."""

    def __init__(self, column_expr: ColumnExpr, fill_value: Any) -> None:
        self.column_expr = column_expr
        self.fill_value = fill_value

    @property
    def name(self) -> str | None:
        return self.column_expr.name

    def to_polars(self) -> pl.Expr:
        target = self.column_expr.to_polars()
        if isinstance(self.fill_value, ColumnExpr):
            val_expr = self.fill_value.to_polars()
            return target.fill_null(val_expr)
        if isinstance(self.fill_value, pl.Expr):
            return target.fill_null(self.fill_value)
        return target.fill_null(pl.lit(self.fill_value))

    def __repr__(self) -> str:
        return f"{self.column_expr}.fill({self.fill_value!r})"


class StringNamespace:
    """Accessor for string methods on a ColumnExpr (c.name.str.starts_with(...))."""

    def __init__(self, parent: ColumnExpr) -> None:
        self._parent = parent

    def starts_with(self, prefix: str) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().str.starts_with(prefix))

    def ends_with(self, suffix: str) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().str.ends_with(suffix))

    def contains(self, pattern: str, literal: bool = True) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().str.contains(pattern, literal=literal))

    def len(self) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().str.len_bytes())

    def to_upper(self) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().str.to_uppercase())

    def to_lower(self) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().str.to_lowercase())

    def strip(self) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().str.strip_chars())

    def replace(self, pattern: str, value: str, literal: bool = True) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().str.replace(pattern, value, literal=literal))

    def split(self, by: str) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().str.split(by))

    def slice(self, offset: int, length: int | None = None) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().str.slice(offset, length))


class DatetimeNamespace:
    """Accessor for datetime methods on a ColumnExpr (c.date.dt.year())."""

    def __init__(self, parent: ColumnExpr) -> None:
        self._parent = parent

    def year(self) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().dt.year())

    def month(self) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().dt.month())

    def day(self) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().dt.day())

    def hour(self) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().dt.hour())

    def minute(self) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().dt.minute())

    def second(self) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().dt.second())

    def date(self) -> ColumnExpr:
        return ColumnExpr(self._parent.to_polars().dt.date())


class ColumnExpr:
    """Core expression building block representing a column or computed tabular expression."""

    def __init__(
        self,
        expr: pl.Expr | str,
        name: str | None = None,
        is_named_only: bool = False,
    ) -> None:
        if isinstance(expr, str):
            self._expr = pl.col(expr)
            self._name = expr
            self._is_named_only = True
        else:
            self._expr = expr
            self._name = name
            self._is_named_only = is_named_only

    @property
    def name(self) -> str | None:
        return self._name

    @property
    def is_named_only(self) -> bool:
        return self._is_named_only

    def to_polars(self) -> pl.Expr:
        return self._expr

    @property
    def str(self) -> StringNamespace:
        return StringNamespace(self)

    @property
    def dt(self) -> DatetimeNamespace:
        return DatetimeNamespace(self)

    # --- Slicing / Range ---
    def to(self, other: ColumnExpr | str) -> RangeExpr:
        if not self._name:
            raise ValueError(f"Cannot form range: starting column '{self}' has no column name")
        return RangeExpr(self._name, other)

    # --- Sorting ---
    def asc(self) -> SortExpr:
        return SortExpr(self, descending=False)

    def desc(self) -> SortExpr:
        return SortExpr(self, descending=True)

    # --- Imputation / Fillna ---
    def fill(self, value: Any) -> FillExpr:
        return FillExpr(self, value)

    # --- Null Checks ---
    def is_null(self) -> ColumnExpr:
        return ColumnExpr(self._expr.is_null())

    def is_not_null(self) -> ColumnExpr:
        return ColumnExpr(self._expr.is_not_null())

    # --- Membership ---
    def is_in(self, values: Sequence[Any]) -> ColumnExpr:
        return ColumnExpr(self._expr.is_in(values))

    # --- Math & Aggregations ---
    def sum(self) -> ColumnExpr:
        return ColumnExpr(self._expr.sum())

    def mean(self) -> ColumnExpr:
        return ColumnExpr(self._expr.mean())

    def median(self) -> ColumnExpr:
        return ColumnExpr(self._expr.median())

    def min(self) -> ColumnExpr:
        return ColumnExpr(self._expr.min())

    def max(self) -> ColumnExpr:
        return ColumnExpr(self._expr.max())

    def std(self) -> ColumnExpr:
        return ColumnExpr(self._expr.std())

    def var(self) -> ColumnExpr:
        return ColumnExpr(self._expr.var())

    def count(self) -> ColumnExpr:
        return ColumnExpr(self._expr.count())

    def round(self, decimals: int = 0) -> ColumnExpr:
        return ColumnExpr(self._expr.round(decimals))

    def abs(self) -> ColumnExpr:
        return ColumnExpr(self._expr.abs())

    # --- Rolling Windows ---
    def rolling_mean(self, window_size: int, min_periods: int | None = None, center: bool = False) -> ColumnExpr:
        return ColumnExpr(self._expr.rolling_mean(window_size=window_size, min_samples=min_periods, center=center))

    def rolling_sum(self, window_size: int, min_periods: int | None = None, center: bool = False) -> ColumnExpr:
        return ColumnExpr(self._expr.rolling_sum(window_size=window_size, min_samples=min_periods, center=center))

    def rolling_std(self, window_size: int, min_periods: int | None = None, center: bool = False) -> ColumnExpr:
        return ColumnExpr(self._expr.rolling_std(window_size=window_size, min_samples=min_periods, center=center))

    def rolling_min(self, window_size: int, min_periods: int | None = None, center: bool = False) -> ColumnExpr:
        return ColumnExpr(self._expr.rolling_min(window_size=window_size, min_samples=min_periods, center=center))

    def rolling_max(self, window_size: int, min_periods: int | None = None, center: bool = False) -> ColumnExpr:
        return ColumnExpr(self._expr.rolling_max(window_size=window_size, min_samples=min_periods, center=center))

    # --- Cast ---
    def cast(self, dtype: Any) -> ColumnExpr:
        return ColumnExpr(self._expr.cast(dtype))

    # --- Comparisons ---
    def __eq__(self, other: Any) -> ColumnExpr:  # type: ignore[override]
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr == val)

    def __ne__(self, other: Any) -> ColumnExpr:  # type: ignore[override]
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr != val)

    def __lt__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr < val)

    def __le__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr <= val)

    def __gt__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr > val)

    def __ge__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr >= val)

    # --- Boolean Logic ---
    def __and__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr & val)

    def __rand__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(val & self._expr)

    def __or__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr | val)

    def __ror__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(val | self._expr)

    def __invert__(self) -> Any:
        """If named only, inverting acts as an ExclusionExpr for select(); otherwise boolean not."""
        if self._is_named_only:
            return ExclusionExpr(self)
        return ColumnExpr(self._expr.not_())

    # --- Arithmetic ---
    def __add__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr + val)

    def __radd__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(val + self._expr)

    def __sub__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr - val)

    def __rsub__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(val - self._expr)

    def __mul__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr * val)

    def __rmul__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(val * self._expr)

    def __truediv__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr / val)

    def __rtruediv__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(val / self._expr)

    def __floordiv__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr // val)

    def __rfloordiv__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(val // self._expr)

    def __mod__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr % val)

    def __rmod__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(val % self._expr)

    def __pow__(self, other: Any) -> ColumnExpr:
        val = other.to_polars() if isinstance(other, ColumnExpr) else pl.lit(other)
        return ColumnExpr(self._expr ** val)

    def __neg__(self) -> ColumnExpr:
        return ColumnExpr(-self._expr)

    def __abs__(self) -> ColumnExpr:
        return ColumnExpr(self._expr.abs())

    def __repr__(self) -> str:
        if self._is_named_only and self._name:
            return f"c.{self._name}"
        return f"ColumnExpr({self._expr})"


class ColumnProxy:
    """The universal `c` column proxy factory.

    Supports:
      c.column_name        -> ColumnExpr
      c["Column Name"]     -> ColumnExpr (for spaces / special characters)
      c.start.to(c.end)    -> RangeExpr
    """

    def __getattr__(self, name: str) -> ColumnExpr:
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        return ColumnExpr(expr=name, is_named_only=True)

    def __getitem__(self, item: Any) -> ColumnExpr:
        if isinstance(item, str):
            return ColumnExpr(expr=item, is_named_only=True)
        if isinstance(item, ColumnExpr):
            return item
        raise TypeError(f"Column index must be str, got {type(item).__name__}: {item!r}")

    def __repr__(self) -> str:
        return "<pytae ColumnProxy 'c'>"


# Global singleton instance
c = ColumnProxy()
col = c
