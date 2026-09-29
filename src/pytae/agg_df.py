from __future__ import annotations

import difflib
from collections.abc import Sequence
from typing import Any

import pandas as pd

from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name
from pytae.cli_parsing import parse_agg as _parse_agg

_UNSET = object()


def _safe_parse_agg(raw: str) -> Any:
    try:
        return _parse_agg(raw)
    except SystemExit as exc:
        msg = str(exc)
        if msg.startswith("-agg: "):
            msg = f"agg(): {msg[6:]}"
        raise ValueError(msg) from exc
_KNOWN_AGGS = {
    "mean",
    "sum",
    "std",
    "var",
    "min",
    "max",
    "count",
    "size",
    "median",
    "first",
    "last",
    "n",
    "prod",
    "sem",
    "skew",
    "kurt",
}


def _agg_df_list(
    df: pd.DataFrame,
    group_cols: list[str],
    agg_types: str | list[str],
    dropna: bool,
    observed: bool,
) -> pd.DataFrame:
    """Helper function to handle string/list aggfunc for agg_df.

    Applies aggregations to all numeric columns (excluding group_cols).
    """
    agg_types = [agg_types] if isinstance(agg_types, str) else list(agg_types)
    unique_agg_types = list(dict.fromkeys(agg_types))  # Remove duplicates, preserve order
    remaining_agg_types = [agg for agg in unique_agg_types if agg != "n"]
    has_n = "n" in unique_agg_types

    numeric_cols = [col for col in df.select_dtypes(include=["number"]).columns if col not in group_cols]

    if has_n and "n" in numeric_cols:
        raise ValueError(
            "agg_df: cannot compute 'n' (row count) because the input already has a "
            "numeric column named 'n'; rename that column first, or use the kwargs form "
            "(e.g. df.pt.agg(by='...', n_col='n')) to pick a different count-column name."
        )
    if has_n and "n" in group_cols:
        raise ValueError(
            "agg_df: cannot compute 'n' (row count) because the input already has a "
            "group column named 'n'; rename that column first, or use the kwargs form "
            "(e.g. df.pt.agg(by='...', n_col='n')) to pick a different count-column name."
        )

    if not numeric_cols and not has_n:
        raise ValueError("No numeric columns to aggregate and 'n' not specified")

    if group_cols:
        if has_n and not numeric_cols:
            grouped_df = df.groupby(group_cols, dropna=dropna, observed=observed).size().reset_index(name="n")
            return grouped_df

        agg_operations = {col: remaining_agg_types for col in numeric_cols}
        try:
            grouped_df = df.groupby(group_cols, as_index=False, dropna=dropna, observed=observed).agg(agg_operations)
        except (AttributeError, ValueError) as exc:
            raise ValueError(f"agg(): invalid aggregation function ({exc})") from exc

        # Flatten MultiIndex in columns
        if len(remaining_agg_types) > 1:
            flattened = [
                col[0] if (len(col) > 1 and not col[1]) else (f"{col[0]}_{col[1]}" if len(col) > 1 else str(col[0]))
                for col in grouped_df.columns.values
            ]
        else:
            flattened = [col[0] for col in grouped_df.columns.values]

        non_group_cols = [c for i, c in enumerate(flattened) if i >= len(group_cols)]
        for col in non_group_cols:
            if col in group_cols:
                raise ValueError(f"agg_df: output column name '{col}' collides with group column '{col}'")
        if len(non_group_cols) != len(set(non_group_cols)):
            counts: dict[str, int] = {}
            for col in non_group_cols:
                counts[col] = counts.get(col, 0) + 1
            dups = [col for col, count in counts.items() if count > 1]
            raise ValueError(f"agg_df: output column name '{dups[0]}' is duplicated in aggregation output")
        if has_n and "n" in non_group_cols:
            raise ValueError("agg_df: output column name 'n' collides with count column 'n'")

        grouped_df.columns = flattened

        if has_n:
            grouped_df["n"] = df.groupby(group_cols, dropna=dropna, observed=observed).size().values

        g_cols = group_cols + (["n"] if has_n else [])
        remaining_cols = [col for col in grouped_df.columns if col not in g_cols]
        return grouped_df.reindex(columns=g_cols + remaining_cols)
    else:
        # Whole-table summary (1 row, no groups)
        if has_n and not numeric_cols:
            return pd.DataFrame({"n": [len(df)]})

        row_dict: dict[str, list[Any]] = {}
        if has_n:
            row_dict["n"] = [len(df)]

        for col in numeric_cols:
            for agg in remaining_agg_types:
                col_name = f"{col}_{agg}" if len(remaining_agg_types) > 1 else col
                if col_name in row_dict:
                    raise ValueError(f"agg_df: output column name '{col_name}' is duplicated in aggregation specification")
                s = df[col]
                try:
                    val = getattr(s, agg)() if hasattr(s, agg) and callable(getattr(s, agg)) else s.agg(agg)
                except Exception as exc:
                    raise ValueError(f"agg(): invalid aggregation function {agg!r} ({exc})") from exc
                row_dict[col_name] = [val]

        return pd.DataFrame(row_dict)


def _agg_df_dict(
    df: pd.DataFrame,
    group_cols: list[str],
    agg_types: dict[str, Any],
    dropna: bool,
    observed: bool,
) -> pd.DataFrame:
    """Helper function to handle keyword/dictionary aggfunc for agg_df.

    Applies aggregations to specified columns, with 'n' keys used for count column names.
    Supports named aggregations like total='v1:sum' or total=('v1', 'sum').
    Output columns follow dictionary order after group columns.
    """
    output_cols = []
    named_aggs: dict[str, tuple[str, str]] = {}
    count_cols = []

    for out_name, spec in agg_types.items():
        clean_out_name = _unquote_name(out_name)
        if spec == "n" or spec == ["n"] or spec == ("n",):
            if clean_out_name in group_cols:
                raise ValueError(
                    f"agg_df: count output name '{clean_out_name}' collides with group column '{clean_out_name}'"
                )
            if clean_out_name in output_cols:
                raise ValueError(f"agg_df: output column name '{clean_out_name}' is duplicated in aggregation specification")
            count_cols.append(clean_out_name)
            output_cols.append(clean_out_name)
            continue

        if isinstance(spec, str) and ":" in spec:
            src_col, aggfunc = spec.split(":", 1)
            src_col, aggfunc = _unquote_name(src_col.strip()), aggfunc.strip()
            aggfunc_clean = _unquote_name(aggfunc)
            if "," in aggfunc_clean:
                aggs_list = [s.strip() for s in aggfunc_clean.split(",") if s.strip()]
            else:
                aggs_list = [aggfunc_clean]
        elif isinstance(spec, tuple) and len(spec) == 2 and _unquote_name(spec[0]) in df.columns:
            src_col = _unquote_name(spec[0])
            aggfunc = spec[1]
            aggs_list = [aggfunc] if isinstance(aggfunc, str) else list(aggfunc)
        else:
            src_col = clean_out_name
            if isinstance(spec, str):
                spec_clean = _unquote_name(spec)
                if "," in spec_clean:
                    aggs_list = [s.strip() for s in spec_clean.split(",") if s.strip()]
                else:
                    aggs_list = [spec]
            elif isinstance(spec, (list, tuple, set)):
                aggs_list = list(spec)
            else:
                aggs_list = [spec]

        aggs_list = list(dict.fromkeys(aggs_list))  # preserve order
        if "n" in aggs_list:
            raise ValueError(f"'n' cannot be used as an aggregation function for column '{clean_out_name}' in a dictionary aggfunc")
        if src_col not in df.columns:
            raise KeyError(f"Column '{src_col}' does not exist in DataFrame")
        if src_col in group_cols:
            raise ValueError(f"Column '{src_col}' is already a grouping column in 'by'")
        if not pd.api.types.is_numeric_dtype(df[src_col]):
            raise ValueError(f"Column '{src_col}' is not numeric")

        if not aggs_list:
            raise ValueError(f"No valid aggregation functions specified for column '{src_col}'")

        def _record_output_col(name: str, src: str, fn: str) -> None:
            if name in group_cols:
                raise ValueError(f"agg_df: output column name '{name}' collides with group column '{name}'")
            if name in output_cols:
                raise ValueError(f"agg_df: output column name '{name}' is duplicated in aggregation specification")
            output_cols.append(name)
            named_aggs[name] = (src, fn)

        if src_col == clean_out_name:
            if len(aggs_list) > 1:
                for agg_fn in aggs_list:
                    _record_output_col(f"{src_col}_{agg_fn}", src_col, agg_fn)
            else:
                _record_output_col(src_col, src_col, aggs_list[0])
        else:
            if len(aggs_list) > 1:
                for agg_fn in aggs_list:
                    _record_output_col(f"{clean_out_name}_{agg_fn}", src_col, agg_fn)
            else:
                _record_output_col(clean_out_name, src_col, aggs_list[0])


    if group_cols:
        if not named_aggs and count_cols:
            grouped_df = df.groupby(group_cols, dropna=dropna, observed=observed).size().reset_index(name="n")
            result = grouped_df[group_cols].copy()
            for count_col in count_cols:
                result[count_col] = grouped_df["n"]
            return result.reindex(columns=group_cols + count_cols)

        if not named_aggs:
            raise ValueError("No valid numeric aggregations specified")

        grouped_df = df.groupby(group_cols, as_index=False, dropna=dropna, observed=observed).agg(**named_aggs)

        if count_cols:
            counts = df.groupby(group_cols, dropna=dropna, observed=observed).size().values
            for count_col in count_cols:
                grouped_df[count_col] = counts

        final_cols = group_cols + output_cols
        return grouped_df.reindex(columns=final_cols)
    else:
        # Whole-table summary (1 row, no groups)
        if not named_aggs and not count_cols:
            raise ValueError("No aggregations specified")

        row_dict: dict[str, list[Any]] = {}
        for count_col in count_cols:
            row_dict[count_col] = [len(df)]

        for out_name, (src_col, agg_fn) in named_aggs.items():
            s = df[src_col]
            val = getattr(s, agg_fn)() if hasattr(s, agg_fn) and callable(getattr(s, agg_fn)) else s.agg(agg_fn)
            row_dict[out_name] = [val]

        df_out = pd.DataFrame(row_dict)
        return df_out.reindex(columns=output_cols)


def agg_df(
    df: pd.DataFrame,
    by: str | Sequence[str] | None = _UNSET,  # type: ignore[assignment]
    *args: Any,
    **kwargs: Any,
) -> pd.DataFrame:
    """Aggregate a DataFrame grouped by explicit `by` column(s).

    Parameters:
    -----------
    df : pd.DataFrame
        The pandas DataFrame to aggregate.
    by : str, Sequence[str], or None
        Grouping column name(s). Pass None to perform a whole-table summary (grand total, 1 row).
        Can be passed positionally as the first argument or via keyword `by=` / `group_by=`.
    *args : str or list of str
        Aggregation specification(s):
        - Column mapping string(s) (e.g., 'tip = mean, [total bill] = mean, n = n' or
          'tip = mean', '[total bill] = mean', 'n = n'). Brackets [...] enclose columns with spaces.
        - Whole-frame aggregation function(s) applied to all numeric columns:
          - If str (e.g., 'mean', or 'mean, n'): Apply to all numeric columns.
          - If list (e.g., ['mean', 'n']): Apply listed aggregations. 'n' computes group row counts.
    **kwargs :
        - Column aggregations passed as keyword arguments (e.g. df.pt.agg('species', body_mass_g='mean', count='n')).
          Keys with value 'n' specify the output column name for group row counts.
          Supports named aggregations like total='v1:sum'.
        - a (str or list, optional): Whole-frame or mapping aggregation function(s) when passed as keyword `a=`.
        - dropna (bool): Whether to drop NA values in groupby. Defaults to False.
        - observed (bool): Whether to show only observed values for categorical groupby columns. Defaults to True.

    Returns:
    --------
    pd.DataFrame
        Aggregated DataFrame with group columns, count 'n' (if requested), and aggregated metrics.
    """
    if "group_by" in kwargs:
        if "by" in kwargs or by is not _UNSET:
            raise TypeError("agg() got multiple values for argument 'by'/'group_by'")
        by = kwargs.pop("group_by")
    elif "by" in kwargs:
        if by is not _UNSET:
            raise TypeError("agg() got multiple values for argument 'by'")
        by = kwargs.pop("by")

    if by is _UNSET:
        raise TypeError(
            "agg() missing required argument: 'by'. "
            "Specify grouping column(s) as first argument (e.g. df.pt.agg('species', 'mean')), "
            "or None for whole-table summary (e.g. df.pt.agg(None, 'mean'))."
        )

    if isinstance(by, dict):
        raise TypeError(
            "agg() no longer accepts dictionaries. Pass column aggregations as string mapping "
            "(e.g. df.pt.agg('by_col', 'col = mean, n = n')) or keyword arguments: "
            "df.pt.agg('by_col', body_mass_g='mean', count='n')."
        )

    # Check if user mistakenly passed an aggregation name as 'by'
    if isinstance(by, str):
        clean_by = _unquote_name(by)
        if clean_by in df.columns:
            by = clean_by
        else:
            tokens = [_unquote_name(t.strip()) for t in _tokenize(by, ",", keep_quotes=True, track_brackets=True) if t.strip()]
            if len(tokens) > 1:
                by = tokens
            else:
                if by.lower() in _KNOWN_AGGS:
                    raise ValueError(
                        f"agg(): '{by}' is not a column in DataFrame, but is a known aggregation function. "
                        "The first argument to agg() must be 'by' (group column(s), or None for whole-table summary). "
                        f"Did you mean: df.pt.agg(None, {by!r}) or df.pt.agg(by='col', a={by!r})?"
                    )
                close = difflib.get_close_matches(clean_by, df.columns, n=1)
                hint = f" (did you mean '{close[0]}'?)" if close else ""
                raise KeyError(f"agg(): group column '{by}' not found in DataFrame{hint}")

    if isinstance(by, (list, tuple)):
        by = [_unquote_name(x) if isinstance(x, str) else x for x in by]
        if by and all(isinstance(x, str) and x.lower() in _KNOWN_AGGS for x in by) and not any(x in df.columns for x in by):
            raise ValueError(
                f"agg(): {list(by)!r} looks like an aggregation list, but the first argument to agg() must be 'by' "
                "(group column(s), or None for whole-table summary). "
                f"Did you mean: df.pt.agg(None, {list(by)!r}) or df.pt.agg(by='col', a={list(by)!r})?"
            )
        for col in by:
            if col not in df.columns:
                close = difflib.get_close_matches(str(col), df.columns, n=1)
                hint = f" (did you mean '{close[0]}'?)" if close else ""
                raise KeyError(f"agg(): group column '{col}' not found in DataFrame{hint}")


    if by is None:
        group_cols: list[str] = []
    elif isinstance(by, str):
        group_cols = [by]
    elif isinstance(by, (list, tuple)):
        group_cols = list(by)
    else:
        raise TypeError(f"'by' must be a column name (str), list of column names, or None, got {type(by).__name__}")

    # Extract aggregation spec
    col_kwargs = {k: v for k, v in kwargs.items() if k not in ("dropna", "observed", "a")}
    has_a = "a" in kwargs
    a_arg = kwargs.pop("a", None)

    if args and has_a:
        raise TypeError("agg() got multiple values for aggregation spec ('a' and positional args)")

    agg_types: Any
    if args:
        if isinstance(args[0], dict):
            raise TypeError(
                "agg() no longer accepts dictionaries. Pass column aggregations as string mapping "
                "(e.g. df.pt.agg('by_col', 'col = mean, n = n')) or keyword arguments: "
                "df.pt.agg('by_col', body_mass_g='mean', count='n')."
            )
        if all(isinstance(x, str) for x in args):
            raw_spec = ", ".join(args)
            parsed = _safe_parse_agg(raw_spec)
            if isinstance(parsed, dict):
                if col_kwargs:
                    parsed.update(col_kwargs)
                agg_types = parsed
            else:
                if col_kwargs:
                    raise ValueError(
                        "agg(): cannot mix whole-frame aggregation string with column keyword arguments; "
                        "use one or the other"
                    )
                agg_types = parsed
        elif len(args) == 1 and isinstance(args[0], (list, tuple)):
            if col_kwargs:
                raise ValueError(
                    "agg(): cannot mix whole-frame aggregation list with column keyword arguments; "
                    "use one or the other"
                )
            agg_types = list(args[0])
        elif len(args) == 1:
            agg_types = args[0]
        else:
            raise ValueError(f"agg(): unsupported positional arguments {args!r}")
    elif has_a:
        if isinstance(a_arg, dict):
            raise TypeError(
                "agg() no longer accepts dictionaries. Pass column aggregations as string mapping "
                "(e.g. df.pt.agg('by_col', 'col = mean, n = n')) or keyword arguments: "
                "df.pt.agg('by_col', body_mass_g='mean', count='n')."
            )
        if isinstance(a_arg, str):
            parsed = _safe_parse_agg(a_arg)
            if isinstance(parsed, dict):
                if col_kwargs:
                    parsed.update(col_kwargs)
                agg_types = parsed
            else:
                if col_kwargs:
                    raise ValueError(
                        "agg(): cannot mix whole-frame aggregation string with column keyword arguments; "
                        "use one or the other"
                    )
                agg_types = parsed
        elif isinstance(a_arg, (list, tuple)):
            if col_kwargs:
                raise ValueError(
                    "agg(): cannot mix whole-frame aggregation list with column keyword arguments; "
                    "use one or the other"
                )
            agg_types = list(a_arg)
        else:
            agg_types = a_arg
    else:
        agg_types = col_kwargs if col_kwargs else ["sum"]

    dropna = kwargs.get("dropna", False)
    observed = kwargs.get("observed", True)

    if isinstance(agg_types, dict):
        return _agg_df_dict(df, group_cols, agg_types, dropna, observed)
    else:
        return _agg_df_list(df, group_cols, agg_types, dropna, observed)


# Alias: agg is identical to agg_df
agg = agg_df