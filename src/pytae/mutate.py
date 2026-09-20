from __future__ import annotations

import difflib
import inspect

import numpy as np
import pandas as pd
from pandas.errors import UndefinedVariableError

from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name


def _split_mutate_entries(raw: str) -> list[tuple[str, str]]:
    """Split a mutate spec into raw (key, expression) text pairs on top-level
    commas/colons, respecting quotes and nested (), [], {} — same tokenizing
    convention as qry()'s conditions dict."""
    entries: list[tuple[str, str]] = []
    for raw_entry in _tokenize(raw, ",", keep_quotes=True, track_brackets=True):
        if not raw_entry:
            continue
        pieces = _tokenize(raw_entry, ":", keep_quotes=True, track_brackets=True)
        if len(pieces) < 2:
            raise ValueError(f"invalid mutate spec: missing ':' in entry '{raw_entry}'")
        entries.append((pieces[0], ":".join(pieces[1:])))
    return entries


def parse_mutate_spec(raw: str) -> dict:
    """Parse a mutate spec string like "bmi: body_mass_g / bill_length_mm ** 2,
    mass_kg: body_mass_g / 1000" into an ordered {new_col: expression} dict.
    Quoting the key is optional (matches qry()); the expression is kept as raw
    text — column names inside it must stay unquoted, since eval() treats a
    quoted name as a string literal, not a column reference."""
    stripped = raw.strip()
    expressions: dict = {}
    for key_raw, expr_raw in _split_mutate_entries(stripped):
        key = _unquote_name(key_raw)
        if not key:
            raise ValueError("invalid mutate spec: empty column name")
        expr = expr_raw.strip()
        if not expr:
            raise ValueError(f"invalid mutate spec: '{key}' has no expression")
        expressions[key] = expr
    if not expressions:
        raise ValueError('mutate expects entries like "col: expr"')
    return expressions


def _parse_call(expr: str, name: str) -> list[str] | None:
    """If expr is exactly `name(...)`, return its top-level comma-separated
    argument strings (quote/bracket-aware); otherwise None."""
    stripped = expr.strip()
    prefix = f"{name}("
    if not stripped.startswith(prefix) or not stripped.endswith(")"):
        return None
    inner = stripped[len(prefix) : -1].strip()
    if not inner:
        return []
    return _tokenize(inner, ",", keep_quotes=True, track_brackets=True)


def _eval(out: pd.DataFrame, expr: str, local_dict: dict, global_dict: dict):
    """out.eval(expr), resolving @local_var references against the scope that
    called mutate() rather than mutate()'s own frame — mutate() sits between
    the user's call and this eval(), so pandas' default frame-walking would
    otherwise look in the wrong place."""
    return out.eval(expr, local_dict=local_dict, global_dict=global_dict)


def _eval_value_arg(out: pd.DataFrame, arg: str, local_dict: dict, global_dict: dict):
    """Evaluate one if_else()/case_when() value argument: a quoted string is
    taken literally (broadcast as-is), anything else is a pandas eval()
    expression (a number, or a column/arithmetic expression)."""
    arg = arg.strip()
    if len(arg) >= 2 and arg[0] == arg[-1] and arg[0] in "'\"":
        return arg[1:-1]
    return _eval(out, arg, local_dict, global_dict)


def _apply_if_else(out: pd.DataFrame, args: list[str], local_dict: dict, global_dict: dict):
    """if_else(condition, true_value, false_value) -> np.where(...)."""
    if len(args) != 3:
        raise ValueError(f"if_else expects 3 arguments (condition, true_value, false_value), got {len(args)}")
    condition = _eval(out, args[0], local_dict, global_dict)
    true_value = _eval_value_arg(out, args[1], local_dict, global_dict)
    false_value = _eval_value_arg(out, args[2], local_dict, global_dict)
    try:
        return np.where(condition, true_value, false_value)
    except TypeError:
        # branches with incompatible dtypes (e.g. a string branch and a numeric
        # branch) have no common numpy dtype -- object arrays accept anything
        return np.where(condition, np.asarray(true_value, dtype=object), np.asarray(false_value, dtype=object))


def _apply_case_when(out: pd.DataFrame, args: list[str], local_dict: dict, global_dict: dict):
    """case_when(cond1: val1, cond2: val2, ..., default) -> np.select(...).
    Entries are checked in order, first match wins. A last argument with no
    colon is the catch-all default (like SQL ELSE); unmatched rows are NaN
    if it is omitted."""
    if not args:
        raise ValueError("case_when expects at least one 'condition: value' entry")
    conditions = []
    choices = []
    default = None
    for i, raw_entry in enumerate(args):
        pieces = _tokenize(raw_entry, ":", keep_quotes=True, track_brackets=True)
        if len(pieces) < 2:
            if i != len(args) - 1:
                raise ValueError(
                    f"invalid case_when entry '{raw_entry}': expected 'condition: value' "
                    "(a bare default must be last)"
                )
            default = _eval_value_arg(out, raw_entry, local_dict, global_dict)
            continue
        condition_raw = pieces[0].strip()
        value_raw = ":".join(pieces[1:]).strip()
        conditions.append(_eval(out, condition_raw, local_dict, global_dict))
        choices.append(_eval_value_arg(out, value_raw, local_dict, global_dict))
    if not conditions:
        raise ValueError("case_when needs at least one non-default condition")
    try:
        return np.select(conditions, choices, default=default)
    except TypeError:
        # choices/default with incompatible dtypes have no common numpy dtype --
        # object arrays accept anything (same fallback as _apply_if_else above)
        choices = [np.asarray(choice, dtype=object) for choice in choices]
        default = default if default is None else np.asarray(default, dtype=object)
        return np.select(conditions, choices, default=default)


def mutate(df, spec: str) -> pd.DataFrame:
    """
    Create or overwrite columns from a qry()-style spec string, each evaluated in
    order via pandas eval() — no lambda needed for plain arithmetic/boolean column
    assignments (e.g. "bmi: body_mass_g / bill_length_mm ** 2").

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame to mutate columns on.
    spec : str
        Entries like "new_col: expression", comma-separated; quoting the key is
        optional (matches qry()). The expression is normally pandas eval() syntax
        (e.g. "body_mass_g / bill_length_mm ** 2") — column names in it must stay
        unquoted, since quoting one turns it into a string literal instead of a
        column reference. Later entries may reference columns derived by
        earlier entries in the same call. A local variable from the caller's
        scope can be referenced with an `@` prefix, e.g. "flag: body_mass_g >=
        @threshold" (matches pandas eval()/query()'s own `@` convention).

        Two special expression forms (dplyr-style) bypass eval() to support
        conditional/string outcomes, which eval() itself cannot express:
          - "result: if_else(condition, true_value, false_value)" — like R's
            `if_else()`. Backed by `np.where()`.
          - "result: case_when(cond1: val1, cond2: val2, ..., default)" —
            like R's `case_when()`. Conditions are checked in order, first match
            wins; a last argument with no colon is an optional catch-all default
            (like SQL ELSE) and must be listed last. Unmatched rows are NaN if
            no default is given. Backed by `np.select()`.
        In both forms, `condition`/`true_value`/`false_value`/`cond*` are eval()
        expressions (unquoted column names), while string outcomes need quotes
        (e.g. `"Pass"`).

    Returns:
    --------
    pd.DataFrame
        A copy of df with each key assigned the result of its expression,
        applied in order.

    Examples:
    ---------
    >>> import pandas as pd
    >>> df = pd.DataFrame({'body_mass_g': [3000.0, 4000.0], 'bill_length_mm': [30.0, 40.0]})
    >>> df.mutate("bmi: body_mass_g / bill_length_mm ** 2")
       body_mass_g  bill_length_mm       bmi
    0       3000.0            30.0  3.333333
    1       4000.0            40.0  2.500000

    >>> # later entries can reference columns derived earlier in the same call
    >>> df.mutate("mass_kg: body_mass_g / 1000, mass_lb: mass_kg * 2.20462")
       body_mass_g  bill_length_mm  mass_kg    mass_lb
    0       3000.0            30.0      3.0   6.613860
    1       4000.0            40.0      4.0   8.818480

    >>> # dplyr-style if_else()/case_when() for conditional/string outcomes
    >>> df.mutate("result: if_else(body_mass_g >= 3500, 'heavy', 'light')")
       body_mass_g  bill_length_mm  result
    0       3000.0            30.0   light
    1       4000.0            40.0   heavy

    >>> df.mutate("grade: case_when(body_mass_g >= 3800: 'A', body_mass_g >= 3200: 'B', 'C')")
       body_mass_g  bill_length_mm grade
    0       3000.0            30.0     C
    1       4000.0            40.0     A
    """
    caller_frame = inspect.currentframe().f_back
    local_dict = caller_frame.f_locals
    global_dict = caller_frame.f_globals
    del caller_frame  # avoid holding a reference cycle via the frame object

    expressions = parse_mutate_spec(spec)
    out = df.copy()
    for col, expr in expressions.items():
        try:
            if_else_args = _parse_call(expr, "if_else")
            case_when_args = _parse_call(expr, "case_when")
            if if_else_args is not None:
                out[col] = _apply_if_else(out, if_else_args, local_dict, global_dict)
            elif case_when_args is not None:
                out[col] = _apply_case_when(out, case_when_args, local_dict, global_dict)
            else:
                out[col] = _eval(out, expr, local_dict, global_dict)
        except UndefinedVariableError as exc:
            close = difflib.get_close_matches(str(exc).split("'")[1], list(out.columns), n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            raise KeyError(f"mutate: '{col}': {exc}{hint}") from exc
    return out
