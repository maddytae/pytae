from __future__ import annotations

import ast
import difflib
import inspect
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.errors import UndefinedVariableError

from pytae._text import tokenize as _tokenize
from pytae._text import unquote_name as _unquote_name


def _split_mutate_entries(raw: str) -> list[tuple[str, str]]:
    """Split a mutate spec into raw (key, expression) text pairs on top-level
    commas/newlines/equals/colons, respecting quotes and nested (), [], {} — same tokenizing
    convention as qry()'s conditions dict. Lines starting with # are stripped."""
    lines = [line for line in raw.splitlines() if not line.strip().startswith("#")]
    cleaned = "\n".join(lines)
    entries: list[tuple[str, str]] = []
    for raw_entry in _tokenize(cleaned, ",\n", keep_quotes=True, track_brackets=True):
        if not raw_entry:
            continue
        # Support '=' as primary assignment operator (ignoring ==, <=, >=, !=)
        m_eq = re.match(
            r"^((?:[^\x22\x27\[\]=]|\x22[^\x22]*\x22|\x27[^\x27]*\x27|\[[^\]]*\])+?)(?<![<>!=])=(?!=)(.+)$",
            raw_entry,
        )
        if m_eq:
            entries.append((m_eq.group(1).strip(), m_eq.group(2).strip()))
            continue
        pieces = _tokenize(raw_entry, ":", keep_quotes=True, track_brackets=True)
        if len(pieces) >= 2:
            raise ValueError(f"invalid mutate spec: use '=' for assignment (e.g. 'col = expr'). Colon ':' is not supported in entry '{raw_entry}'")
        raise ValueError(f"invalid mutate spec: missing '=' in entry '{raw_entry}'")
    return entries


def parse_mutate_spec(raw: str) -> dict[str, str]:
    """Parse a mutate spec string like "bmi = body_mass_g / bill_length_mm ** 2,
    mass_kg = body_mass_g / 1000" into an ordered {new_col: expression} dict.
    If raw starts with '@', it reads the spec from the specified file path.
    Quoting the key is optional (matches qry()); the expression is kept as raw
    text — column names inside it must stay unquoted, since eval() treats a
    quoted name as a string literal, not a column reference."""
    stripped = raw.strip()
    if (stripped.startswith("'") and stripped.endswith("'")) or (stripped.startswith('"') and stripped.endswith('"')):
        stripped = stripped[1:-1].strip()
    if stripped.startswith("@"):
        path = stripped[1:].strip()
        if (path.startswith("'") and path.endswith("'")) or (path.startswith('"') and path.endswith('"')):
            path = path[1:-1].strip()
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"mutate spec file not found: '{path}'")
        stripped = file_path.read_text(encoding="utf-8").strip()
    expressions: dict[str, str] = {}
    for key_raw, expr_raw in _split_mutate_entries(stripped):
        key = _unquote_name(key_raw)
        if not key:
            raise ValueError("invalid mutate spec: empty column name")
        expr = expr_raw.strip()
        if not expr:
            raise ValueError(f"invalid mutate spec: '{key}' has no expression")
        expressions[key] = expr
    if not expressions:
        raise ValueError('mutate expects entries like "col = expr"')
    return expressions


_NO_MAP_DEFAULT = object()


def _map_values(series, mapping, default=_NO_MAP_DEFAULT):
    """map(column, mapping[, default]) helper injected into the fallback eval
    namespace: recode a column's values through a lookup (dict or Series), like
    pandas Series.map(). Keys with no match become `default` if given, else
    NaN."""
    s = pd.Series(series)
    result = s.map(mapping)
    if default is not _NO_MAP_DEFAULT:
        keys = set(mapping.keys()) if hasattr(mapping, "keys") else (set(mapping.index) if hasattr(mapping, "index") else set(mapping))
        is_missing_key = ~s.isin(keys)
        result = result.mask(is_missing_key, default)
    return result


def _result_index(*candidates):
    """Index for a helper's Series result: the first Series among its inputs
    (a condition/branch/choice), so the result aligns on assignment and supports
    .str/.dt/etc. chaining. None (RangeIndex) if no input is a Series."""
    for candidate in candidates:
        if isinstance(candidate, pd.Series):
            return candidate.index
    return None


def _clean_condition(cond):
    if isinstance(cond, pd.Series):
        return cond.fillna(False).to_numpy(dtype=bool)
    if isinstance(cond, (list, tuple)):
        return pd.Series(cond).fillna(False).to_numpy(dtype=bool)
    return cond


def _if_else(condition, true_value, false_value):
    """if_else(condition, true_value, false_value) helper injected into the
    fallback eval namespace -> np.where(...), returned as a Series so it chains
    and composes like any pandas Series."""
    clean_cond = _clean_condition(condition)
    try:
        result = np.where(clean_cond, true_value, false_value)
    except TypeError:
        # incompatible dtypes across branches have no common numpy dtype --
        # object arrays accept anything
        result = np.where(
            clean_cond,
            np.asarray(true_value, dtype=object),
            np.asarray(false_value, dtype=object),
        )
    if getattr(result, "ndim", None) == 0:
        return result.item()
    return pd.Series(result, index=_result_index(condition, true_value, false_value))


def _case_when(*entries, default=None):
    """case_when((cond, value), ..., [default=...]) helper injected into the fallback
    eval namespace -> np.select(...), returned as a Series so it chains and
    composes. Each positional arg can be a (condition, value) pair checked in order
    (first match wins); a trailing non-tuple arg or `default=` keyword argument
    is the catch-all default (unmatched rows are NaN if omitted).
    Also supports flat alternating arguments: case_when(c1, v1, c2, v2, default=d)."""
    if not entries:
        raise ValueError("case_when expects at least one (condition, value) pair")
    conditions, choices = [], []
    has_tuple = any(isinstance(e, tuple) for e in entries)
    if not has_tuple:
        flat_entries = list(entries)
        if len(flat_entries) % 2 == 1:
            if default is not None:
                raise ValueError("case_when received an odd number of flat arguments and an explicit default=")
            default = flat_entries.pop()
        if len(flat_entries) < 2:
            raise ValueError("case_when needs at least one (condition, value) pair")
        for i in range(0, len(flat_entries), 2):
            conditions.append(flat_entries[i])
            choices.append(flat_entries[i + 1])
    else:
        for i, entry in enumerate(entries):
            if isinstance(entry, tuple):
                if len(entry) != 2:
                    raise ValueError(f"case_when pair must be (condition, value), got a {len(entry)}-tuple")
                condition, value = entry
                conditions.append(condition)
                choices.append(value)
            elif i == len(entries) - 1:
                if default is not None:
                    raise ValueError("case_when default specified both positionally and via keyword")
                default = entry
            else:
                raise ValueError("case_when default (a non-tuple) must be the last argument")
    if not conditions:
        raise ValueError("case_when needs at least one (condition, value) pair")
    clean_conditions = [_clean_condition(c) for c in conditions]
    try:
        result = np.select(clean_conditions, choices, default=default)
    except TypeError:
        # incompatible dtypes across choices/default -- object arrays accept anything
        object_choices = [np.asarray(choice, dtype=object) for choice in choices]
        object_default = default if default is None else np.asarray(default, dtype=object)
        result = np.select(clean_conditions, object_choices, default=object_default)  # type: ignore[arg-type]
    if getattr(result, "ndim", None) == 0:
        return result.item()
    return pd.Series(result, index=_result_index(*conditions, *choices))


def _coalesce(*candidates):
    """coalesce(col1, col2, ..., default) helper injected into the fallback eval namespace:
    returns the first non-null value for each row, like SQL COALESCE() or dplyr::coalesce()."""
    if not candidates:
        raise ValueError("coalesce expects at least one argument")
    series_candidates = [c for c in candidates if isinstance(c, pd.Series)]
    if not series_candidates:
        for c in candidates:
            if c is not None and not (isinstance(c, float) and np.isnan(c)) and not pd.isna(c):
                return c
        return None

    target_index = series_candidates[0].index
    res = None
    for cand in candidates:
        if isinstance(cand, pd.Series):
            s = cand if cand.index.equals(target_index) else cand.reindex(target_index)
            res = s.copy() if res is None else res.combine_first(s)
        else:
            s = pd.Series(cand, index=target_index)
            res = s if res is None else res.fillna(cand)
    return res


def _normalize_col_brackets(expr: str, columns: set[str]) -> str:
    """Rewrite [col] to `col` when col is a known DataFrame column, outside string literals."""
    out_chars: list[str] = []
    quote = None
    i, n = 0, len(expr)
    while i < n:
        ch = expr[i]
        if quote is not None:
            out_chars.append(ch)
            if ch == "\\" and i + 1 < n:
                out_chars.append(expr[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out_chars.append(ch)
            i += 1
            continue
        if ch == "[":
            j = expr.find("]", i + 1)
            if j != -1:
                inner = expr[i + 1 : j]
                if inner in columns:
                    out_chars.append(f"`{inner}`")
                    i = j + 1
                    continue
        out_chars.append(ch)
        i += 1
    return "".join(out_chars)


def _rewrite_fallback_col_refs(expr: str, columns: set[str]) -> tuple[str, dict[str, str]]:
    """Rewrite `col` and [col] for known columns to synthetic identifiers like __col_safe_0__
    for the plain Python eval() fallback, outside string literals."""
    out_chars: list[str] = []
    quote = None
    i, n = 0, len(expr)
    mapping: dict[str, str] = {}
    col_idx = 0
    while i < n:
        ch = expr[i]
        if quote is not None:
            out_chars.append(ch)
            if ch == "\\" and i + 1 < n:
                out_chars.append(expr[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out_chars.append(ch)
            i += 1
            continue
        if ch == "`":
            j = expr.find("`", i + 1)
            if j != -1:
                inner = expr[i + 1 : j]
                if inner in columns:
                    alias = f"__col_safe_{col_idx}__"
                    col_idx += 1
                    mapping[alias] = inner
                    out_chars.append(alias)
                    i = j + 1
                    continue
        if ch == "[":
            j = expr.find("]", i + 1)
            if j != -1:
                inner = expr[i + 1 : j]
                if inner in columns:
                    alias = f"__col_safe_{col_idx}__"
                    col_idx += 1
                    mapping[alias] = inner
                    out_chars.append(alias)
                    i = j + 1
                    continue
        out_chars.append(ch)
        i += 1
    return "".join(out_chars), mapping


def _strip_at_refs(expr: str) -> tuple[str, set[str]]:
    """Rewrite pandas-eval `@name` local-variable refs to bare `name` for the
    plain Python eval() fallback (which has no `@` syntax), and report which
    names were referenced. `@` inside string literals is left untouched."""
    out_chars: list[str] = []
    names: set[str] = set()
    quote = None
    i, n = 0, len(expr)
    while i < n:
        ch = expr[i]
        if quote is not None:
            out_chars.append(ch)
            if ch == "\\" and i + 1 < n:
                out_chars.append(expr[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            out_chars.append(ch)
            i += 1
            continue
        if ch == "@" and i + 1 < n and (expr[i + 1].isalpha() or expr[i + 1] == "_"):
            j = i + 1
            while j < n and (expr[j].isalnum() or expr[j] == "_"):
                j += 1
            names.add(expr[i + 1 : j])
            out_chars.append(expr[i + 1 : j])
            i = j
            continue
        out_chars.append(ch)
        i += 1
    return "".join(out_chars), names


class _Lit:
    """Wrapper marking a value as an explicit literal constant in mutate()."""

    def __init__(self, value: Any):
        self.value = value

    def __repr__(self) -> str:
        return f"lit({self.value!r})"


def lit(value: Any) -> _Lit:
    """Mark a value as an explicit literal constant in mutate().

    In mutate(), string arguments are evaluated as formulas/column expressions.
    Passing pt.lit(val) ensures the value is assigned directly as a literal constant
    rather than evaluated as a column name (avoiding 'name is not defined' errors
    or accidental column aliasing):
        df.pt.mutate(status=pt.lit("active"))
        df.pt.mutate(source=pt.lit("original"))
    """
    return _Lit(value)


class _BoolOpRewriter(ast.NodeTransformer):
    """Rewrite `and`/`or`/`not` to `&`/`|`/`~` for the Python-eval fallback, so
    boolean conditions on a Series work (plain `and`/`or` on a Series raises
    "ambiguous truth value"). Also rewrites `lit(identifier)` to literal string constants.
    Done on the AST, so operand grouping/precedence is preserved automatically.
    Matches pandas eval()'s own and/or translation."""

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        op: ast.operator = ast.BitAnd() if isinstance(node.op, ast.And) else ast.BitOr()
        folded = node.values[0]
        for right in node.values[1:]:
            folded = ast.BinOp(left=folded, op=op, right=right)
        return folded

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.op, ast.Not):
            return ast.UnaryOp(op=ast.Invert(), operand=node.operand)
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        is_lit = False
        if isinstance(node.func, ast.Name) and node.func.id == "lit":
            is_lit = True
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "lit"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in ("pt", "pytae")
        ):
            is_lit = True
        if is_lit and len(node.args) == 1:
            arg = node.args[0]
            if isinstance(arg, ast.Name):
                return ast.Constant(value=arg.id)
            if isinstance(arg, ast.Constant):
                return arg
        return node


def _compile_fallback(expr: str):
    """Parse a fallback expression and rewrite its boolean operators, returning a
    code object ready for eval()."""
    tree = ast.parse(expr, mode="eval")
    tree = _BoolOpRewriter().visit(tree)
    ast.fix_missing_locations(tree)
    return compile(tree, "<pytae-mutate>", "eval")


class _RowCount(int):
    """Integer that can also be called as a function n() to match dplyr/polars conventions."""

    def __call__(self) -> int:
        return int(self)


def _eval(out: pd.DataFrame, expr: str, local_dict: dict, global_dict: dict):
    """out.eval(expr), resolving @local_var references against the scope that
    called mutate() rather than mutate()'s own frame — mutate() sits between
    the user's call and this eval(), so pandas' default frame-walking would
    otherwise look in the wrong place.

    pandas' eval() can't parse some Python constructs (notably dict literals,
    e.g. `species.map({'a': 1})`, string slicing like `col.str[:8]`, and custom
    helpers like `if_else`, `case_when`, `coalesce`); when it rejects one
    (NotImplementedError, ValueError, SyntaxError, or UndefinedVariableError) we fall back
    to a plain Python eval() with each column exposed as a Series plus the caller's scope,
    so natural pandas method chains work. Bracketed `[col]` and backtick `col`
    names are safely mapped to valid identifiers in fallback mode. `@name` refs
    are rewritten to the caller-scope value, and `and`/`or`/`not` are rewritten
    to `&`/`|`/`~` so boolean conditions on a Series work."""
    known_cols = set(out.columns)
    normalized = _normalize_col_brackets(expr, known_cols)
    try:
        return out.eval(normalized, local_dict=local_dict, global_dict=global_dict)
    except (NotImplementedError, ValueError, SyntaxError, UndefinedVariableError):
        safe_expr, col_map = _rewrite_fallback_col_refs(expr, known_cols)
        rewritten, at_names = _strip_at_refs(safe_expr)
        namespace = {**global_dict, **local_dict}
        namespace["map"] = _map_values  # prefix map(col, {...}[, default]) form
        namespace["if_else"] = _if_else
        namespace["case_when"] = _case_when
        namespace["coalesce"] = _coalesce
        namespace["lit"] = lambda val: val.value if isinstance(val, _Lit) else val

        class _PtLitHolder:
            lit = staticmethod(lambda val: val.value if isinstance(val, _Lit) else val)

        if "pt" not in namespace:
            namespace["pt"] = _PtLitHolder
        namespace["mean"] = lambda s: s.mean() if hasattr(s, "mean") else np.mean(s)
        namespace["sum"] = lambda s: s.sum() if hasattr(s, "sum") else np.sum(s)
        namespace["median"] = lambda s: s.median() if hasattr(s, "median") else np.median(s)
        namespace["min"] = lambda s: s.min() if hasattr(s, "min") else np.min(s)
        namespace["max"] = lambda s: s.max() if hasattr(s, "max") else np.max(s)
        namespace["std"] = lambda s: s.std() if hasattr(s, "std") else np.std(s)
        namespace["var"] = lambda s: s.var() if hasattr(s, "var") else np.var(s)
        if "n" not in out.columns:
            namespace["n"] = _RowCount(len(out))
        namespace.update({col: out[col] for col in out.columns if col.isidentifier()})
        for alias, orig_col in col_map.items():
            namespace[alias] = out[orig_col]
        for name in at_names:  # @-refs mean caller-scope vars, so they win over columns
            if name in local_dict:
                namespace[name] = local_dict[name]
            elif name in global_dict:
                namespace[name] = global_dict[name]
            else:
                raise UndefinedVariableError(f"local variable '{name}' is not defined")
        return eval(_compile_fallback(rewritten), namespace)  # noqa: S307 - spec is developer-authored, same trust as pandas eval


def mutate(
    df: pd.DataFrame,
    *args: Any,
    dropna: bool = False,
    observed: bool = True,
    **kwargs: Any,
) -> pd.DataFrame:
    """
    Create or overwrite columns using string expressions (`"col = expr"` or `col="expr"`),
    callables (`col=callable`), or dictionaries. Each evaluated in order via pandas eval().

    Parameters:
    -----------
    df : pd.DataFrame
        The DataFrame to mutate columns on. Inherits active grouping if set via `pt.by()` or `.pt.by()`.
    *args : str or dict
        Positional expressions:
        - String expression(s), e.g. "bmi = body_mass_g / bill_length_mm ** 2".
        - File path prefixed with '@' (e.g. "@transforms.txt").
        - Dictionary of column expressions, e.g. {"bmi": "body_mass_g / 1000"}.
    dropna : bool, default False
        Whether to drop NA groups when evaluating grouped window transformations. Defaults to False.
    observed : bool, default True
        Whether to observe categorical levels when evaluating grouped window transformations.
    params : dict, optional
        Explicit dictionary of parameters/variables to make available for `@name` references.
        Can also be passed via `_params=`.
    **kwargs : Any
        Column expressions or callables passed as keyword arguments,
        e.g. `df.pt.mutate(bmi="body_mass_g / bill_length_mm ** 2", rank=1)`.
    """
    if "by" in kwargs or "_by" in kwargs:
        raise TypeError("mutate() does not accept 'by'. Set grouping beforehand using pt.by(df, 'col') or df.pt.by('col').")

    _here = inspect.currentframe()
    caller_frame = None if _here is None else _here.f_back
    del _here
    while caller_frame is not None:
        # skip pytae internals (df.pt.mutate() sits in the accessor)
        name = caller_frame.f_globals.get("__name__") or ""
        if not name.startswith("pytae"):
            break
        caller_frame = caller_frame.f_back
    local_dict = caller_frame.f_locals.copy() if caller_frame is not None else {}
    global_dict = caller_frame.f_globals if caller_frame is not None else {}
    del caller_frame  # avoid holding a reference cycle via the frame object

    dropna = kwargs.pop("dropna", dropna)
    observed = kwargs.pop("observed", observed)

    by_cols: list[str] | None = list(df.attrs["_pt_by"]) if "_pt_by" in df.attrs else None
    if by_cols is not None:
        all_cols = list(df.columns)
        for col in by_cols:
            if col not in df.columns:
                close = difflib.get_close_matches(str(col), [str(c) for c in all_cols], n=1)
                hint = f" (did you mean '{close[0]}'?)" if close else ""
                raise KeyError(f"mutate: grouping column '{col}' not found in DataFrame{hint}")

    params = kwargs.pop("_params", None)
    if params is None and "params" in kwargs and isinstance(kwargs["params"], dict):
        params = kwargs.pop("params")

    if params is not None:
        local_dict.update(params)

    expressions: dict[str, Any] = {}
    for arg in args:
        if isinstance(arg, str):
            expressions.update(parse_mutate_spec(arg))
        elif isinstance(arg, dict):
            expressions.update(arg)
        elif callable(arg):
            raise TypeError(
                "mutate() expects callables as keyword arguments with the column name, "
                "e.g. df.pt.mutate(new_col=lambda d: d['x'] * 2)"
            )
        else:
            raise TypeError(
                f"mutate() received unexpected positional argument of type {type(arg).__name__}. "
                "Pass string expressions (e.g. 'col = expr'), a dict, or keyword arguments."
            )

    if kwargs:
        expressions.update(kwargs)

    if not expressions:
        raise ValueError(
            "mutate() expects at least one expression, e.g. df.pt.mutate('col = expr') "
            "or df.pt.mutate(col='expr')"
        )

    out = df.copy()
    for col, expr in expressions.items():
        try:
            if by_cols is None:
                if isinstance(expr, _Lit):
                    out[col] = expr.value
                elif callable(expr):
                    out[col] = expr(out)
                elif isinstance(expr, str):
                    out[col] = _eval(out, expr, local_dict, global_dict)
                else:
                    out[col] = expr
            else:
                work_df = out.copy(deep=False)
                work_df["__pt_pos__"] = np.arange(len(out))
                pieces = []
                for _, group_df in work_df.groupby(by_cols, dropna=dropna, observed=observed):
                    pos = group_df["__pt_pos__"].to_numpy()
                    clean_group = group_df.drop(columns=["__pt_pos__"])
                    if isinstance(expr, _Lit):
                        val = expr.value
                    elif callable(expr):
                        val = expr(clean_group)
                    elif isinstance(expr, str):
                        val = _eval(clean_group, expr, local_dict, global_dict)
                    else:
                        val = expr
                    if isinstance(val, pd.Series):
                        pieces.append(pd.Series(val.to_numpy(), index=pos))
                    else:
                        pieces.append(pd.Series(val, index=pos))
                if pieces:
                    combined = pd.concat(pieces).sort_index().reindex(np.arange(len(out)))
                    out[col] = combined.array
                else:
                    out[col] = pd.Series(index=out.index, dtype=float)
        except NameError as exc:  # UndefinedVariableError (pandas) and plain NameError (fallback)
            parts = str(exc).split("'")
            missing = parts[1] if len(parts) > 1 else ""
            close = difflib.get_close_matches(missing, list(out.columns), n=1) if missing else []
            hint = (
                f" (did you mean '{close[0]}'?)"
                if close
                else f" (if you intended a string literal, quote it like '{missing}')"
            )
            raise KeyError(f"mutate: '{col}': {exc}{hint}") from exc
    return out
