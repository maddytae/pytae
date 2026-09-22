from __future__ import annotations

import ast
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


_NO_MAP_DEFAULT = object()


def _map_values(series, mapping, default=_NO_MAP_DEFAULT):
    """map(column, mapping[, default]) helper injected into the fallback eval
    namespace: recode a column's values through a lookup (dict or Series), like
    pandas Series.map(). Keys with no match become `default` if given, else
    NaN."""
    result = pd.Series(series).map(mapping)
    if default is not _NO_MAP_DEFAULT:
        result = result.where(result.notna(), default)
    return result


def _result_index(*candidates):
    """Index for a helper's Series result: the first Series among its inputs
    (a condition/branch/choice), so the result aligns on assignment and supports
    .str/.dt/etc. chaining. None (RangeIndex) if no input is a Series."""
    for candidate in candidates:
        if isinstance(candidate, pd.Series):
            return candidate.index
    return None


def _if_else(condition, true_value, false_value):
    """if_else(condition, true_value, false_value) helper injected into the
    fallback eval namespace -> np.where(...), returned as a Series so it chains
    and composes like any pandas Series."""
    try:
        result = np.where(condition, true_value, false_value)
    except TypeError:
        # incompatible dtypes across branches have no common numpy dtype --
        # object arrays accept anything
        result = np.where(
            condition,
            np.asarray(true_value, dtype=object),
            np.asarray(false_value, dtype=object),
        )
    return pd.Series(result, index=_result_index(condition, true_value, false_value))


def _case_when(*entries):
    """case_when((cond, value), ..., [default]) helper injected into the fallback
    eval namespace -> np.select(...), returned as a Series so it chains and
    composes. Each positional arg is a (condition, value) pair checked in order
    (first match wins); a trailing non-tuple arg is the catch-all default
    (unmatched rows are NaN if omitted)."""
    if not entries:
        raise ValueError("case_when expects at least one (condition, value) pair")
    conditions, choices, default = [], [], None
    for i, entry in enumerate(entries):
        if isinstance(entry, tuple):
            if len(entry) != 2:
                raise ValueError(f"case_when pair must be (condition, value), got a {len(entry)}-tuple")
            condition, value = entry
            conditions.append(condition)
            choices.append(value)
        elif i == len(entries) - 1:
            default = entry
        else:
            raise ValueError("case_when default (a non-tuple) must be the last argument")
    if not conditions:
        raise ValueError("case_when needs at least one (condition, value) pair")
    try:
        result = np.select(conditions, choices, default=default)  # type: ignore[arg-type]
    except TypeError:
        # incompatible dtypes across choices/default -- object arrays accept anything
        object_choices = [np.asarray(choice, dtype=object) for choice in choices]
        object_default = default if default is None else np.asarray(default, dtype=object)
        result = np.select(conditions, object_choices, default=object_default)  # type: ignore[arg-type]
    return pd.Series(result, index=_result_index(*conditions, *choices))


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


class _BoolOpRewriter(ast.NodeTransformer):
    """Rewrite `and`/`or`/`not` to `&`/`|`/`~` for the Python-eval fallback, so
    boolean conditions on a Series work (plain `and`/`or` on a Series raises
    "ambiguous truth value"). Done on the AST, so operand grouping/precedence is
    preserved automatically. Matches pandas eval()'s own and/or translation."""

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


def _compile_fallback(expr: str):
    """Parse a fallback expression and rewrite its boolean operators, returning a
    code object ready for eval()."""
    tree = ast.parse(expr, mode="eval")
    tree = _BoolOpRewriter().visit(tree)
    ast.fix_missing_locations(tree)
    return compile(tree, "<pytae-mutate>", "eval")


def _eval(out: pd.DataFrame, expr: str, local_dict: dict, global_dict: dict):
    """out.eval(expr), resolving @local_var references against the scope that
    called mutate() rather than mutate()'s own frame — mutate() sits between
    the user's call and this eval(), so pandas' default frame-walking would
    otherwise look in the wrong place.

    pandas' eval() can't parse some Python constructs (notably dict literals,
    e.g. `species.map({'a': 1})`, and string slicing like `col.str[:8]`); when
    it rejects one (NotImplementedError, or ValueError for unsupported
    functions such as slicing) we fall back to a plain Python eval() with each
    column exposed as a Series plus the caller's scope, so natural pandas method
    chains work. `@name` refs are rewritten to the caller-scope value so they
    keep working in the fallback, and `and`/`or`/`not` are rewritten to
    `&`/`|`/`~` so boolean conditions on a Series work. UndefinedVariableError
    (an unknown column) is a NameError subclass, so it is not caught here and
    still surfaces mutate()'s typo suggestion."""
    try:
        return out.eval(expr, local_dict=local_dict, global_dict=global_dict)
    except (NotImplementedError, ValueError):
        rewritten, at_names = _strip_at_refs(expr)
        namespace = {**global_dict, **local_dict}
        namespace.update({col: out[col] for col in out.columns})
        namespace["map"] = _map_values  # prefix map(col, {...}[, default]) form
        namespace["if_else"] = _if_else
        namespace["case_when"] = _case_when
        for name in at_names:  # @-refs mean caller-scope vars, so they win over columns
            if name in local_dict:
                namespace[name] = local_dict[name]
            elif name in global_dict:
                namespace[name] = global_dict[name]
            else:
                raise UndefinedVariableError(f"local variable '{name}' is not defined")
        return eval(_compile_fallback(rewritten), namespace)  # noqa: S307 - spec is developer-authored, same trust as pandas eval


def mutate(df: pd.DataFrame, spec: str) -> pd.DataFrame:
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

        Three dplyr-style helpers are available as ordinary function calls, so
        they compose with each other and with any pandas method chain:
          - "result: if_else(condition, true_value, false_value)" — like R's
            `if_else()`. Backed by `np.where()`.
          - "result: case_when((cond1, val1), (cond2, val2), ..., default)" —
            like R's `case_when()`. Each (condition, value) pair is checked in
            order, first match wins; a trailing bare argument is an optional
            catch-all default (like SQL ELSE). Unmatched rows are NaN if no
            default is given. Backed by `np.select()`.
          - "result: map(column, {key: value, ...}[, default])" — recode a
            column through a lookup, like pandas `Series.map()`. Keys with no
            match become `default` (NaN if omitted).
        String outcomes need quotes (e.g. `'Pass'`); column names stay unquoted.
        Conditions are vectorized: prefer `and`/`or`/`not` (the bitwise
        `&`/`|`/`~` also work), parenthesizing when mixing with comparisons.
        Because the helpers are ordinary calls they nest and chain freely, e.g.
        "x: if_else(m >= 4000, map(s, {'G': 'g'}), 'small').str.upper()".

        Any other expression is evaluated with pandas eval(), falling back to a
        plain Python eval() (with each column exposed as a Series) for constructs
        pandas eval() can't parse — dict literals, string slicing like
        `col.str[:8]`, and the helper calls above — so natural pandas method
        chains work, e.g. "code: species.map({'Adelie': 'A'}).fillna('X')".

    Returns:
    --------
    pd.DataFrame
        A copy of df with each key assigned the result of its expression,
        applied in order.

    Examples:
    ---------
    >>> import pandas as pd
    >>> import pytae as pt
    >>> df = pd.DataFrame({'body_mass_g': [3000.0, 4000.0], 'bill_length_mm': [30.0, 40.0]})
    >>> df.pt.mutate("bmi: body_mass_g / bill_length_mm ** 2")
       body_mass_g  bill_length_mm       bmi
    0       3000.0            30.0  3.333333
    1       4000.0            40.0  2.500000

    >>> # later entries can reference columns derived earlier in the same call
    >>> df.pt.mutate("mass_kg: body_mass_g / 1000, mass_lb: mass_kg * 2.20462")
       body_mass_g  bill_length_mm  mass_kg  mass_lb
    0       3000.0            30.0      3.0  6.61386
    1       4000.0            40.0      4.0  8.81848

    >>> # dplyr-style if_else()/case_when() for conditional/string outcomes
    >>> df.pt.mutate("result: if_else(body_mass_g >= 3500, 'heavy', 'light')")
       body_mass_g  bill_length_mm result
    0       3000.0            30.0  light
    1       4000.0            40.0  heavy

    >>> df.pt.mutate("grade: case_when((body_mass_g >= 3800, 'A'), (body_mass_g >= 3200, 'B'), 'C')")
       body_mass_g  bill_length_mm grade
    0       3000.0            30.0     C
    1       4000.0            40.0     A

    >>> # natural pandas method chains work (dict literals + Series.map(), etc.)
    >>> s = pd.DataFrame({'species': ['Adelie', 'Gentoo', 'Chinstrap']})
    >>> s.pt.mutate("code: species.map({'Adelie': 'A', 'Gentoo': 'G'}).fillna('X')")
         species code
    0     Adelie    A
    1     Gentoo    G
    2  Chinstrap    X
    """
    _here = inspect.currentframe()
    caller_frame = None if _here is None else _here.f_back
    del _here
    while caller_frame is not None:
        # skip pytae internals (df.pt.mutate() sits in the accessor)
        name = caller_frame.f_globals.get("__name__") or ""
        if not name.startswith("pytae"):
            break
        caller_frame = caller_frame.f_back
    local_dict = caller_frame.f_locals if caller_frame is not None else {}
    global_dict = caller_frame.f_globals if caller_frame is not None else {}
    del caller_frame  # avoid holding a reference cycle via the frame object

    expressions = parse_mutate_spec(spec)
    out = df.copy()
    for col, expr in expressions.items():
        try:
            out[col] = _eval(out, expr, local_dict, global_dict)
        except NameError as exc:  # UndefinedVariableError (pandas) and plain NameError (fallback)
            parts = str(exc).split("'")
            missing = parts[1] if len(parts) > 1 else ""
            close = difflib.get_close_matches(missing, list(out.columns), n=1) if missing else []
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            raise KeyError(f"mutate: '{col}': {exc}{hint}") from exc
    return out

