from __future__ import annotations

import difflib
import re
from collections.abc import Sequence
from typing import Any

from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name


class _EverythingMeta(type):
    def __repr__(cls) -> str:
        return "everything"


class everything(metaclass=_EverythingMeta):
    """Sentinel class/instance representing all remaining unselected columns in pt.select().

    Can be passed either as the class `pt.everything` or called as `pt.everything()`.
    """

    _instance: everything | None = None

    def __new__(cls) -> everything:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "everything()"


def _matches_dtype(dt: Any, target: Any) -> bool:
    """Match a Polars DataType or Pandas dtype against a target type specifier."""
    import polars as pl

    if isinstance(target, (list, tuple)):
        return any(_matches_dtype(dt, t) for t in target)

    if isinstance(target, str):
        t_low = target.lower().strip()
        if t_low in ("numeric", "number"):
            return bool(hasattr(dt, "is_numeric") and dt.is_numeric())
        if t_low == "non_numeric":
            return bool(not (hasattr(dt, "is_numeric") and dt.is_numeric()))
        if t_low in ("datetime", "datetimetz"):
            return bool(hasattr(dt, "is_temporal") and dt.is_temporal())
        if t_low == "category":
            return dt in (pl.Categorical, pl.Enum) or getattr(dt, "base_type", None) == pl.Categorical
        if t_low == "bool":
            return dt == pl.Boolean
        if t_low in ("string", "str"):
            return dt in (pl.String, pl.Utf8)

        dt_str = str(dt).lower().replace("pl.", "").replace("dtype", "")
        return dt_str == t_low or dt_str.startswith(t_low)

    if isinstance(target, pl.DataType):
        return dt == target
    if isinstance(target, type) and issubclass(target, pl.DataType):
        return isinstance(dt, target) or dt == target

    if target is int or (
        isinstance(target, type) and target.__name__ in ("integer", "int", "int64", "int32", "int16", "int8")
    ):
        return bool(hasattr(dt, "is_integer") and dt.is_integer())
    if target is float or (isinstance(target, type) and target.__name__ in ("floating", "float", "float64", "float32")):
        return bool(hasattr(dt, "is_float") and dt.is_float())
    if target is bool or (isinstance(target, type) and target.__name__ in ("bool_", "bool")):
        return dt == pl.Boolean
    if target is str or (isinstance(target, type) and target.__name__ in ("str_", "str")):
        return dt in (pl.String, pl.Utf8)
    if isinstance(target, type) and target.__name__ == "number":
        return bool(hasattr(dt, "is_numeric") and dt.is_numeric())

    return False


def resolve_select_columns(
    all_cols: list[Any],
    schema: Any = None,
    *args: Any,
    exclude: str | Sequence[str] | None = None,
    dtype: str | type | Sequence[str | type] | None = None,
    exclude_dtype: str | type | Sequence[str | type] | None = None,
    contains: str | Sequence[str] | None = None,
    startswith: str | Sequence[str] | None = None,
    endswith: str | Sequence[str] | None = None,
    regex: str | Sequence[str] | None = None,
    df_for_pandas: Any = None,
) -> list[Any]:
    """Resolve column names matching selection criteria without requiring a Pandas DataFrame."""
    if exclude_dtype is not None and (args or exclude or dtype or contains or startswith or endswith or regex):
        raise ValueError("exclude_dtype cannot be combined with other selection criteria.")

    if exclude_dtype is not None:
        if df_for_pandas is not None:
            _shorthands = {
                "numeric": ["number"],
                "datetime": ["datetime", "datetimetz"],
                "category": ["category"],
                "bool": ["bool"],
            }
            if exclude_dtype == "non_numeric":
                return df_for_pandas.select_dtypes(include="number").columns.tolist()
            elif isinstance(exclude_dtype, str) and exclude_dtype in _shorthands:
                return df_for_pandas.select_dtypes(exclude=_shorthands[exclude_dtype]).columns.tolist()
            elif isinstance(exclude_dtype, (str, type)):
                return df_for_pandas.select_dtypes(exclude=[exclude_dtype]).columns.tolist()
            elif isinstance(exclude_dtype, (list, tuple)):
                return df_for_pandas.select_dtypes(exclude=list(exclude_dtype)).columns.tolist()
            else:
                raise TypeError("exclude_dtype must be a string, type, or list of strings/types")

        if schema is not None:
            if exclude_dtype == "non_numeric":
                return [col for col, dt in schema.items() if _matches_dtype(dt, "numeric")]
            elif isinstance(exclude_dtype, (str, type, list, tuple)):
                return [col for col, dt in schema.items() if not _matches_dtype(dt, exclude_dtype)]
            else:
                raise TypeError("exclude_dtype must be a string, type, or list of strings/types")
        return all_cols

    selected_cols: set[Any] = set()
    ordered_cols: list[Any] = []
    excluded_cols: set[Any] = set()
    everything_requested = False

    def _resolve_negation(neg_spec: str) -> list[str]:
        raw = _unquote_name(neg_spec.strip())
        if raw in all_cols:
            return [raw]
        elif ":" in raw:
            start_raw, end_raw = raw.split(":", 1)
            start: str | None = _unquote_name(start_raw.strip()) or None
            end: str | None = _unquote_name(end_raw.strip()) or None
            if start and start not in all_cols:
                raise KeyError(f"Start column '{start}' not found")
            if end and end not in all_cols:
                raise KeyError(f"End column '{end}' not found")
            start_idx = all_cols.index(start) if start in all_cols else 0
            end_idx = all_cols.index(end) if end in all_cols else len(all_cols) - 1
            return all_cols[start_idx : end_idx + 1]
        else:
            close = difflib.get_close_matches(raw, [str(c) for c in all_cols], n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            raise KeyError(f"Column to exclude not found: '{raw}'{hint}")

    if exclude is not None:
        if isinstance(exclude, str):
            raw_exclude = exclude.strip()
            if raw_exclude.startswith("[") and raw_exclude.endswith("]"):
                raw_exclude = raw_exclude[1:-1].strip()
            for token in _tokenize(raw_exclude, ",", keep_quotes=True, track_brackets=True):
                token = _unquote_name(token.strip())
                if token:
                    excluded_cols.update(_resolve_negation(token))
        elif isinstance(exclude, (list, tuple, set)):
            for item in exclude:
                if isinstance(item, str):
                    clean_item = _unquote_name(item.strip())
                    if clean_item.startswith("[") and clean_item.endswith("]"):
                        clean_item = clean_item[1:-1].strip()
                    for sub in _tokenize(clean_item, ",", keep_quotes=True, track_brackets=True):
                        sub = _unquote_name(sub.strip())
                        if sub:
                            excluded_cols.update(_resolve_negation(sub))
                elif item in all_cols:
                    excluded_cols.add(item)
                else:
                    raise KeyError(f"Column to exclude not found: '{item}'")
        else:
            raise TypeError(f"exclude must be a string or sequence of strings, got {type(exclude)}")

    for arg in args:
        if arg is everything or isinstance(arg, everything):
            everything_requested = True
        elif isinstance(arg, list):
            for col in arg:
                clean_col = _unquote_name(col) if isinstance(col, str) else col
                if col in all_cols:
                    selected_cols.add(col)
                    if col not in ordered_cols:
                        ordered_cols.append(col)
                elif isinstance(clean_col, str) and clean_col in all_cols:
                    selected_cols.add(clean_col)
                    if clean_col not in ordered_cols:
                        ordered_cols.append(clean_col)
                elif isinstance(col, str) and col.startswith(("-", "~", "!")):
                    excluded_cols.update(_resolve_negation(col[1:]))
                else:
                    close = difflib.get_close_matches(str(clean_col), [str(c) for c in all_cols], n=1)
                    hint = f" (did you mean '{close[0]}'?)" if close else ""
                    raise KeyError(f"Column not found: '{col}'{hint}")
        elif isinstance(arg, str):
            clean_arg = _unquote_name(arg)
            if arg in all_cols:
                selected_cols.add(arg)
                if arg not in ordered_cols:
                    ordered_cols.append(arg)
            elif clean_arg in all_cols:
                selected_cols.add(clean_arg)
                if clean_arg not in ordered_cols:
                    ordered_cols.append(clean_arg)
            elif arg.startswith(("-", "~", "!")):
                excluded_cols.update(_resolve_negation(arg[1:]))
            elif ":" in arg:
                start_raw, end_raw = arg.split(":", 1)
                start = _unquote_name(start_raw.strip()) or None
                end = _unquote_name(end_raw.strip()) or None
                start_idx = all_cols.index(start) if start in all_cols else 0
                end_idx = all_cols.index(end) if end in all_cols else len(all_cols) - 1
                if start and start not in all_cols:
                    raise KeyError(f"Start column '{start}' not found")
                if end and end not in all_cols:
                    raise KeyError(f"End column '{end}' not found")
                slice_cols = all_cols[start_idx : end_idx + 1]
                selected_cols.update(slice_cols)
                ordered_cols.extend([col for col in slice_cols if col not in ordered_cols])
            elif "," in arg:
                for sub_token in _tokenize(arg, ",", track_brackets=True):
                    if not sub_token:
                        continue
                    clean_sub = _unquote_name(sub_token)
                    if sub_token in all_cols:
                        selected_cols.add(sub_token)
                        if sub_token not in ordered_cols:
                            ordered_cols.append(sub_token)
                    elif clean_sub in all_cols:
                        selected_cols.add(clean_sub)
                        if clean_sub not in ordered_cols:
                            ordered_cols.append(clean_sub)
                    elif sub_token.startswith(("-", "~", "!")):
                        excluded_cols.update(_resolve_negation(sub_token[1:]))
                    elif ":" in sub_token:
                        s_raw, e_raw = sub_token.split(":", 1)
                        s = _unquote_name(s_raw.strip()) or None
                        e = _unquote_name(e_raw.strip()) or None
                        s_idx = all_cols.index(s) if s in all_cols else 0
                        e_idx = all_cols.index(e) if e in all_cols else len(all_cols) - 1
                        if s and s not in all_cols:
                            raise KeyError(f"Start column '{s}' not found")
                        if e and e not in all_cols:
                            raise KeyError(f"End column '{e}' not found")
                        slice_cols = all_cols[s_idx : e_idx + 1]
                        selected_cols.update(slice_cols)
                        ordered_cols.extend([col for col in slice_cols if col not in ordered_cols])
                    else:
                        close = difflib.get_close_matches(clean_sub, [str(c) for c in all_cols], n=1)
                        hint = f" (did you mean '{close[0]}'?)" if close else ""
                        raise KeyError(f"Column not found: '{sub_token}'{hint}")
            else:
                close = difflib.get_close_matches(clean_arg, [str(c) for c in all_cols], n=1)
                hint = f" (did you mean '{close[0]}'?)" if close else ""
                regex_hint = "; for a regex use select(regex=...)" if any(ch in arg for ch in "^$|*+?()") else ""
                raise KeyError(f"Column not found: '{arg}'{hint}{regex_hint}")

        elif callable(arg):
            func_cols = [col for col in all_cols if arg(col)]
            selected_cols.update(func_cols)
            ordered_cols.extend([col for col in func_cols if col not in ordered_cols])
        else:
            raise TypeError(f"Unsupported argument type: {type(arg)}.")

    if dtype is not None:
        if df_for_pandas is not None:
            if isinstance(dtype, str):
                if dtype == "numeric":
                    dtype_cols = df_for_pandas.select_dtypes(include="number").columns.tolist()
                elif dtype == "non_numeric":
                    dtype_cols = df_for_pandas.select_dtypes(exclude="number").columns.tolist()
                elif dtype == "datetime":
                    dtype_cols = df_for_pandas.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
                elif dtype == "category":
                    dtype_cols = df_for_pandas.select_dtypes(include=["category"]).columns.tolist()
                elif dtype == "bool":
                    dtype_cols = df_for_pandas.select_dtypes(include=["bool"]).columns.tolist()
                else:
                    dtype_cols = df_for_pandas.select_dtypes(include=[dtype]).columns.tolist()
            elif isinstance(dtype, (type, list, tuple)):
                dtype_cols = df_for_pandas.select_dtypes(
                    include=list(dtype) if isinstance(dtype, tuple) else dtype
                ).columns.tolist()
            else:
                raise TypeError(f"dtype must be a string, type, list, or tuple, got {type(dtype)}")
        elif schema is not None:
            if isinstance(dtype, (str, type, list, tuple)):
                dtype_cols = [col for col, dt in schema.items() if _matches_dtype(dt, dtype)]
            else:
                raise TypeError(f"dtype must be a string, type, list, or tuple, got {type(dtype)}")
        else:
            dtype_cols = []
        selected_cols.update(dtype_cols)
        ordered_cols.extend([col for col in dtype_cols if col not in ordered_cols])

    if contains is not None:
        if isinstance(contains, str):
            contains_cols = [col for col in all_cols if contains in str(col)]
        elif isinstance(contains, (list, tuple, Sequence)):
            contains_cols = [col for col in all_cols if any(sub in str(col) for sub in contains)]
        else:
            raise TypeError(f"contains must be a string or sequence of strings, got {type(contains)}")
        selected_cols.update(contains_cols)
        ordered_cols.extend([col for col in contains_cols if col not in ordered_cols])

    if startswith is not None:
        if isinstance(startswith, str):
            startswith_cols = [col for col in all_cols if str(col).startswith(startswith)]
        elif isinstance(startswith, (list, tuple, Sequence)):
            startswith_cols = [col for col in all_cols if any(str(col).startswith(sub) for sub in startswith)]
        else:
            raise TypeError(f"startswith must be a string or sequence of strings, got {type(startswith)}")
        selected_cols.update(startswith_cols)
        ordered_cols.extend([col for col in startswith_cols if col not in ordered_cols])

    if endswith is not None:
        if isinstance(endswith, str):
            endswith_cols = [col for col in all_cols if str(col).endswith(endswith)]
        elif isinstance(endswith, (list, tuple, Sequence)):
            endswith_cols = [col for col in all_cols if any(str(col).endswith(sub) for sub in endswith)]
        else:
            raise TypeError(f"endswith must be a string or sequence of strings, got {type(endswith)}")
        selected_cols.update(endswith_cols)
        ordered_cols.extend([col for col in endswith_cols if col not in ordered_cols])

    if regex is not None:
        patterns = [regex] if isinstance(regex, str) else list(regex)
        try:
            compiled = [re.compile(p) for p in patterns]
        except re.error as exc:
            raise ValueError(f"invalid regex: {exc}") from exc
        regex_cols = [col for col in all_cols if any(p.search(str(col)) for p in compiled)]
        selected_cols.update(regex_cols)
        ordered_cols.extend([col for col in regex_cols if col not in ordered_cols])

    # Final assembly:
    if not ordered_cols:
        if everything_requested or excluded_cols:
            return [col for col in all_cols if col not in excluded_cols]
        return []

    if everything_requested:
        remaining_cols = [col for col in all_cols if col not in selected_cols and col not in excluded_cols]
        ordered_cols.extend(remaining_cols)

    return [col for col in ordered_cols if col not in excluded_cols]


def select(
    df: Any,
    *args: Any,
    exclude: str | Sequence[str] | None = None,
    dtype: str | type | Sequence[str | type] | None = None,
    exclude_dtype: str | type | Sequence[str | type] | None = None,
    contains: str | Sequence[str] | None = None,
    startswith: str | Sequence[str] | None = None,
    endswith: str | Sequence[str] | None = None,
    regex: str | Sequence[str] | None = None,
) -> Any:
    """Select columns from a DataFrame based on names, regex patterns, slices, data types,
    string matching, or exclusions.
    """
    from pytae.dataframe import DataFrame

    if isinstance(df, DataFrame):
        target_cols = resolve_select_columns(
            list(df.columns),
            df.schema,
            *args,
            exclude=exclude,
            dtype=dtype,
            exclude_dtype=exclude_dtype,
            contains=contains,
            startswith=startswith,
            endswith=endswith,
            regex=regex,
        )
        return df.select(*target_cols)

    import polars as pl

    if isinstance(df, (pl.DataFrame, pl.LazyFrame)):
        target_cols = resolve_select_columns(
            list(df.columns),
            df.schema,
            *args,
            exclude=exclude,
            dtype=dtype,
            exclude_dtype=exclude_dtype,
            contains=contains,
            startswith=startswith,
            endswith=endswith,
            regex=regex,
        )
        return df.select(target_cols)

    try:
        import pandas as pd

        if isinstance(df, pd.DataFrame):
            target_cols = resolve_select_columns(
                list(df.columns),
                None,
                *args,
                exclude=exclude,
                dtype=dtype,
                exclude_dtype=exclude_dtype,
                contains=contains,
                startswith=startswith,
                endswith=endswith,
                regex=regex,
                df_for_pandas=df,
            )
            return df[target_cols]
    except ImportError:
        pass

    target_cols = resolve_select_columns(
        list(df.columns),
        getattr(df, "schema", None),
        *args,
        exclude=exclude,
        dtype=dtype,
        exclude_dtype=exclude_dtype,
        contains=contains,
        startswith=startswith,
        endswith=endswith,
        regex=regex,
    )
    return df[target_cols]
