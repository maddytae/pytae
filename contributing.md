# Contributing to pytae

Thank you for your interest in contributing to `pytae`! This document outlines our development workflow and the core engineering principles that guide the library and CLI design.

---

## Core Design Principles & Guidelines

When contributing code, designing new features, or refactoring existing modules in `pytae`, adhere to the following principles:

### 1. Be generous in what you accept, but strictly honest when ambiguous
- **Generous in input**: Accept flexible, ergonomic inputs where the intent is unambiguous—strings or sequences of strings (e.g. `r="a,b"`, `select("x, y")`), brackets for spaced names (`[total bill]`), case-insensitivity where natural, and well-documented aliases (`a=` for `aggfunc=`, `r=` for `rows=`, `n` for row counts). Standalone grouping (`pt.by("species", "island")`) takes column names as positional `*args`.
- **Strictly honest when ambiguous**: When inputs collide, contradict, or produce ambiguous results, **fail fast with a clear, descriptive error**.
  - **No silent renaming or magical suffixes**: Never silently invent artificial names like `col_1`, `year_col`, or `1_1` to work around collisions. If an index name collides with a column name during `reset_index()`, or a pivoted column name collides with an index column, raise a `ValueError`.
  - **No silent fallback guessing**: If an explicit stylesheet, palette, or column reference cannot be resolved or is invalid, raise a `ValueError` or `KeyError` rather than guessing or silently ignoring the instruction.
  - **Guide the user**: Error messages should clearly explain the conflict and tell the user how to fix it (e.g., *"For row counts (a='n'), omit 'v' or specify a non-grouping column"* or did-you-mean suggestions).

### 2. One and only one right way
- *“There should be one—and preferably only one—obvious way to do it.”* (The Zen of Python).
- Keep the public API clean, intentional, and cohesive. Avoid introducing redundant, competing verbs or duplicate flags that do the same thing under different names.
- Every verb has a single, crisp responsibility:
  - `wide()` is **strictly for pure 1-to-1 structural unmelting** without aggregation.
  - `pivot()` is for **Excel-style 2D aggregation matrices** across dimensions (`r, c, v, a`).
  - `long()` is for melting columns to rows.
  - `by()` sets an active, scoped grouping context on the DataFrame.
  - `ungroup()` clears active grouping.
  - `agg()` is for grouped summaries collapsing $N \to K$ rows (or whole-table summaries).
  - `mutate()` is for feature engineering and window calculations preserving $N \to N$ rows.
  - `filter()` is for row filtering.
  - `pick()` is for extreme top/bottom row selection (`order='max'` or `'min'`).
  - `distinct()` is for row deduplication.
  - `arrange()` is for row sorting.
  - `select()` is for column selection and reordering.


### 3. Predictable, flat data structures
- DataFrames produced by `pytae` operations should be clean and immediately usable:
  - Standard integer `RangeIndex(0, 1, 2, ...)` (no lingering MultiIndex on rows or columns).
  - Clean, 1D string column headers.
  - Numerical counts (`a='n'`) return standard integer types (`int64` or nullable `Int64`), not floats.
  - Missing grid intersections default to 0 for count operations (`a='n'`).

### 4. Consistent defaults across CLI and Library
- Defaults are uniform across all verbs:
  - `dropna=False` by default across all operations (`pivot`, `wide`, `agg`, `mutate`, `freq`, `value_counts`, and plotting), preserving missing categories unless explicitly excluded via `dropna=True`.
- Vocabulary is shared across Python and CLI:
  - `r`, `c`, `v`, `a` in `pt.pivot(...)` match `r=`, `c=`, `v=`, `a=` in `-pivot "..."`.
  - `[Column Name]` bracketed quoting works identically across `filter()`, `select()`, `mutate()`, `agg()`, `-sql`, and CLI flags.

### 5. Immutability & Side-Effect Free Chaining
- Accessor calls on `df.pt.<verb>(...)` must never mutate the caller's DataFrame in place. Always return a new or copied DataFrame.
- Methods should chain cleanly in fluent pipelines without requiring intermediate variable assignments.

---

## Development Setup

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/maddytae/pytae.git
cd pytae

# Using uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,notebooks]"

# Or standard pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,notebooks]"
```

---

## Testing & Quality Checks

Before submitting changes, make sure all quality checks pass cleanly:

```bash
# 1. Run the test suite
pytest

# 2. Run linting and code formatting checks
ruff check src/ tests/

# 3. Run static type checking
mypy src/

# 4. Optional: run interactive tutorial notebooks
python scripts/run_notebooks.py
```

> [!NOTE]
> Interactive tutorial notebooks in `docs/library/` are not run on every commit because they exercise end-to-end plotting and file IO. They run automatically in CI on tag releases, or manually via `python scripts/run_notebooks.py`.

---

## Pull Request Guidelines

1. **Write Unit Tests**: Every bug fix, new feature, or error condition must be backed by unit tests in `tests/`.
2. **Keep Errors Informative**: Avoid generic error messages. Use `difflib.get_close_matches` where appropriate to suggest typos.
3. **Update Documentation**: If updating a CLI flag or library verb, update the corresponding documentation in `docs/cli/` and `docs/library/`.
4. **Follow Typing Standards**: pytae is PEP 561 compliant (`py.typed`). All new functions in `src/pytae/` should have comprehensive type annotations.
