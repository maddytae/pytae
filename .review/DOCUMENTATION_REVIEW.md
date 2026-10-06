# Pytae Documentation Review & Verification Audit

This document details findings from verifying all documentation files (`readme.md`, `docs/cli.md`, `docs/library.md`, `docs/comparison.md`, and `docs/cli/*.md`), including factual claim audits, code execution tests, and signature consistency checks.

---

## 1. Factual Inaccuracies & False Claims

### 1.1 [HIGH] Incorrect Explanation of `-pretty` in `docs/cli/other_utilities.md`

- **Document**: [`docs/cli/other_utilities.md`](../docs/cli/other_utilities.md#L30)
- **Claimed in Documentation**:
  > `| -pretty | Formatting | Flag | Formats numbers with thousands commas (1,000,000) in terminal output |`
  >
  > ```bash
  > # Add comma thousand-separators to large counts and numbers
  > pytae sales.parquet -by region -agg "total=revenue:sum" -pretty
  > ```
- **Reality in Code** ([`src/pytae/cli_run.py:47-56`](../src/pytae/cli_run.py#L47-L56)):
  ```python
  def _format_table(df: pd.DataFrame, *, index: bool | None = None, pretty: bool = False) -> str:
      """Render a DataFrame as standard pandas text, or a markdown/bordered table when pretty=True."""
      if not pretty:
          return df.to_string(index=index)
      try:
          return df.to_markdown(index=index)
      except ImportError:
          return df.to_string(index=index)
  ```
  The `-pretty` flag **does not format numbers with thousand-separator commas**. Instead, it renders the DataFrame as a GitHub-flavored Markdown bordered table with pipe characters (`| col1 | col2 |`).
- **Correction Required**:
  Update `docs/cli/other_utilities.md` and `readme.md` to accurately state:
  `-pretty`: Renders terminal output as a formatted Markdown bordered table (using `df.to_markdown()`).

---

### 1.2 [MEDIUM] Inaccurate Description of `-progress`

- **Document**: [`docs/cli/other_utilities.md`](../docs/cli/other_utilities.md#L33)
- **Claimed in Documentation**:
  > `| -progress | Diagnostics | Flag | Displays progress bar for large file operations |`
- **Reality in Code** ([`src/pytae/readers.py:46-51`](../src/pytae/readers.py#L46-L51)):
  ```python
  def _print_progress(done: int, total: int | None, label: str) -> None:
      if total:
          pct = min(100, int(done * 100 / total))
          print(f"\r{label}... {done}/{total} rows ({pct}%)", end="", flush=True)
      else:
          print(f"\r{label}... {done} rows", end="", flush=True)
  ```
  It prints an inline carriage-return status string (`reading... 50000/200000 rows (25%)`), not a graphical progress bar.
- **Correction Required**:
  Clarify that `-progress` displays a live row-count / percentage status stream in the terminal.

---

### 1.3 [LOW] Inaccurate Description of `-pager`

- **Document**: [`docs/cli/other_utilities.md`](../docs/cli/other_utilities.md#L32)
- **Claimed in Documentation**:
  > `Displays terminal output through a scrollable system pager (less)`
- **Reality in Code** ([`src/pytae/cli_run.py:150-155`](../src/pytae/cli_run.py#L150-L155)):
  `-pager` invokes Python's standard `pydoc.pager(text)`, which delegates to the environment's configured `$PAGER` variable (or system default), rather than hardcoding `less`.

---

## 2. API Signature & Default Mismatches

### 2.1 `pt.slice_max` and `pt.slice_min` Signature Drift in Reference Manual

- **Location**: `reference/pytae_reference.txt` & `scripts/generate_reference.py`
- **Documented**:
  `- pt.slice_max(df, order_by, n=1, by=None, with_ties=True)`
- **Actual Signature in `src/pytae/arrange.py`**:
  `def slice_max(df: pd.DataFrame, col: str, n: int = 1, *, by=None, with_ties: bool = False, na_last: bool = True)`
- **Drift Points**:
  1. Parameter is named `col`, not `order_by`. Calling `pt.slice_max(df, order_by='col')` raises `TypeError`.
  2. Default for `with_ties` is `False`, not `True`.
  3. `na_last: bool = True` is omitted from the documented signature.
  4. Parameters after `n` are keyword-only (`*`).

---

### 2.2 `safe_reset_index` Documented as Exported Function

- **Location**: `reference/pytae_reference.txt` lines 33 & 135
- **Documented**:
  `- pt.safe_reset_index(df)`
- **Actual Code**:
  `safe_reset_index` is implemented in `src/pytae/other_utilities.py` but is **not exported** in `src/pytae/__init__.py`. Calling `pt.safe_reset_index(df)` raises `AttributeError`.

---

### 2.3 `pt.mutate` Parameter Documentation

- **Location**: `reference/pytae_reference.txt` line 121
- **Documented**:
  `- pt.mutate(df, *args, by=None, dropna=False, observed=True, params=None, **kwargs)`
- **Actual Signature in `src/pytae/mutate.py`**:
  `def mutate(df, *args, by=None, dropna=False, observed=True, **kwargs)`
- **Notes**:
  `params` is handled inside `kwargs.pop("params")` / `kwargs.pop("_params")` rather than being an explicit parameter in the signature.

---

## 3. Link and Structure Health

- **Total Links Checked in `readme.md`**: 35
  - Broken links found: **0** (100% resolution rate).
- **All 10 Jupyter Notebooks** in `docs/library/` run successfully via `scripts/run_notebooks.py` with zero execution errors:
  - `agg.ipynb` (pass)
  - `arrange.ipynb` (pass)
  - `mutate.ipynb` (pass)
  - `other_utilities.ipynb` (pass)
  - `pivot.ipynb` (pass)
  - `plotting.ipynb` (pass)
  - `qry.ipynb` (pass)
  - `reshape.ipynb` (pass)
  - `select.ipynb` (pass)
  - `sql.ipynb` (pass)
- **Deprecation Cleanliness**:
  - Zero active occurrences of `-query`, `-sort`, `-sort_by`, `-unique`, `-drop_na`, or `agg_df` in documentation code blocks.
