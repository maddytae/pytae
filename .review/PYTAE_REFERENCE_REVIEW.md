# Pytae Reference Manual (`pytae_reference.txt`) Audit

This document reviews `reference/pytae_reference.txt` and its generator script `scripts/generate_reference.py`.

---

## 1. Structure & Architecture

`reference/pytae_reference.txt` is an all-in-one comprehensive knowledge base designed for AI agent training, offline developer search, and complete API reference.

### Scale & Metrics:
- **Total Lines**: 24,927 lines
- **Total Size**: ~950 KB
- **Generator**: [`scripts/generate_reference.py`](../scripts/generate_reference.py)
- **Sections**:
  1. Overview & Core Philosophy
  2. Package Architecture & Import Patterns
  3. Sample Datasets
  4. Python Library Reference (API Verbs)
  5. CLI Reference (Command Line Interface)
  6. Frequently Asked Questions, Pitfalls & Syntax Rules
  7. End-to-End Recipes & Examples
  8. CLI Feature Documentation Guides (`docs/cli/*.md`)
  9. Interactive Library Notebook Walkthroughs (`docs/library/*.ipynb` rendered as Markdown)
  10. Philosophy & Comparison Rosetta Stone (`docs/comparison.md`)
  11. Repository Directory Tree
  12. Build & Configuration (`pyproject.toml`)
  13. Underlying Python Implementation Source Code (`src/pytae/*.py`)
  14. Test Suite Implementation Source Code (`tests/*.py`)

---

## 2. Issues & Discrepancies in the Hand-Authored Reference Text

The first 7 sections of `scripts/generate_reference.py` are hand-maintained in `MANUAL_TEXT`. The following discrepancies were identified between `MANUAL_TEXT` and the actual implementation:

### 2.1 Function Signature Drifts
In **Section 2 (Top-Level Functions exported by `pytae`)**:

1. **`slice_max` and `slice_min`**:
   - `MANUAL_TEXT`:
     `- pt.slice_max(df, order_by, n=1, by=None, with_ties=True)`
     `- pt.slice_min(df, order_by, n=1, by=None, with_ties=True)`
   - Actual Code in `src/pytae/arrange.py`:
     `def slice_max(df: pd.DataFrame, col: str, n: int = 1, *, by: str | Sequence[str] | None = None, with_ties: bool = False, na_last: bool = True) -> pd.DataFrame:`
   - Discrepancies:
     - Parameter name is `col`, not `order_by`.
     - `with_ties` defaults to `False`, not `True`.
     - `na_last: bool = True` is omitted.
     - `by`, `with_ties`, `na_last` are keyword-only (`*`).

2. **`arrange`**:
   - `MANUAL_TEXT`:
     `- pt.arrange(df, *cols)`
   - Actual Code:
     `def arrange(df: pd.DataFrame, *cols: Any, ascending: bool | Sequence[bool] | None = None, na_last: bool = True) -> pd.DataFrame:`
   - Discrepancy: `ascending` and `na_last` are omitted from the parameter list.

3. **`safe_reset_index`**:
   - `MANUAL_TEXT`:
     `- pt.safe_reset_index(df)`
   - Actual Code: Not exported in `src/pytae/__init__.py`. Calling `pt.safe_reset_index(df)` raises `AttributeError`.

4. **`replace_values`**:
   - `MANUAL_TEXT`:
     `- pt.replace_values(df, v: dict, c=None, exact=True)`
   - Actual Code:
     `def replace_values(df: pd.DataFrame, v: dict[Any, Any], c: str | Sequence[str] | None = None, exact: bool = True) -> pd.DataFrame:`

---

## 3. Automation Health & Generation Pipeline

- **Generation Script Execution**:
  `scripts/generate_reference.py` executes without errors and dynamically collects:
  - All 15 Markdown files in `docs/cli/` (including newly created `other_utilities.md`)
  - All 10 interactive notebooks in `docs/library/` (including `arrange.ipynb`)
  - `docs/comparison.md`
  - All source files in `src/pytae/`
  - All test files in `tests/`
- **Cleanliness**:
  Static version numbers (`# latest release: 3.7.0`) have been removed from the reference manual to prevent staleness across releases.

---

## 4. Recommendations for Generator Script

1. **Synchronize `MANUAL_TEXT` Signatures**:
   Update Section 2 in `scripts/generate_reference.py` so signatures precisely match `inspect.signature()` of the actual functions in `src/pytae/`.
2. **Export `safe_reset_index` in `__init__.py`**:
   Export `safe_reset_index` in `src/pytae/__init__.py` so `pt.safe_reset_index(df)` works as documented.
3. **Add `df.pt.to_clip()`**:
   Add `to_clip()` to `PtAccessor` so accessor chaining works seamlessly alongside `df.to_clip()`.
