import difflib

import pandas as pd
from pandas.errors import UndefinedVariableError


def _tokenize(raw: str, seps: str, *, keep_quotes: bool = False, track_brackets: bool = False) -> list[str]:
    """Split raw into segments at top-level occurrences of any character in `seps`,
    respecting quotes and (), [], {} nesting. Duplicated from cli_parsing._tokenize
    on purpose — mutate() is a plain library method and must not import the
    CLI-only cli_parsing module."""
    segments: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    depth = 0
    for ch in raw:
        if quote:
            if ch == quote:
                quote = None
                if keep_quotes:
                    buf.append(ch)
            else:
                buf.append(ch)
            continue
        if ch in "'\"":
            quote = ch
            if keep_quotes:
                buf.append(ch)
        elif track_brackets and ch in "([{":
            depth += 1
            buf.append(ch)
        elif track_brackets and ch in ")]}":
            depth -= 1
            buf.append(ch)
        elif depth == 0 and ch in seps:
            segments.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    segments.append("".join(buf).strip())
    return segments


def _unquote_name(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1]
    return raw


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


def mutate(self, spec: str) -> pd.DataFrame:
    """
    Create or overwrite columns from a qry()-style spec string, each evaluated in
    order via pandas eval() — no lambda needed for plain arithmetic/boolean column
    assignments (e.g. "bmi: body_mass_g / bill_length_mm ** 2").

    Parameters:
    -----------
    self : pd.DataFrame
        The DataFrame to mutate columns on.
    spec : str
        Entries like "new_col: expression", comma-separated; quoting the key is
        optional (matches qry()). The expression is pandas eval() syntax (e.g.
        "body_mass_g / bill_length_mm ** 2") — column names in it must stay
        unquoted, since quoting one turns it into a string literal instead of a
        column reference. Later entries may reference columns derived by
        earlier entries in the same call.

    Limitation:
    -----------
    pandas eval() has no if/else — conditional expressions (`'a' if cond else
    'b'`) and numexpr's where() both raise (confirmed: 'IfExp' nodes are not
    implemented / "where" is not a supported function), regardless of engine.
    A two-branch NUMERIC condition can be built with boolean arithmetic, e.g.
    "bonus: (body_mass_g > 4000) * 100 + (body_mass_g <= 4000) * 10" — but for
    string outcomes or 3+ branches, use plain pandas instead:
    `df.assign(weight_class=lambda d: np.where(d.body_mass_g > 4000, 'heavy', 'light'))`
    or `pd.cut(...)`. mutate() trades that flexibility for zero-lambda simplicity
    on the common case (a single formula per column).

    Returns:
    --------
    pd.DataFrame
        A copy of self with each key assigned the result of its expression,
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
    """
    expressions = parse_mutate_spec(spec)
    out = self.copy()
    for col, expr in expressions.items():
        try:
            out[col] = out.eval(expr)
        except UndefinedVariableError as exc:
            close = difflib.get_close_matches(str(exc).split("'")[1], list(out.columns), n=1)
            hint = f" (did you mean '{close[0]}'?)" if close else ""
            raise KeyError(f"mutate: '{col}': {exc}{hint}") from exc
    return out


# Attach the method to the DataFrame class
pd.DataFrame.mutate = mutate
