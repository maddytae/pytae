# Pytae Core Logic Review & Deep-Dive Audit

This document details findings from a line-by-line review of `pytae`'s core analytical engine, covering `src/pytae/arrange.py`, `src/pytae/agg.py`, `src/pytae/mutate.py`, `src/pytae/select.py`, `src/pytae/shape.py`, `src/pytae/qry.py`, `src/pytae/sql.py`, `src/pytae/other_utilities.py`, and `src/pytae/accessor.py`.

---

## 1. Confirmed Bugs & Critical Logic Flaws

### 1.1 [HIGH SEVERITY] Silent Data Loss in `slice_max` and `slice_min` When Grouping Columns Contain `NaN`

- **Location**: [`src/pytae/arrange.py`](../src/pytae/arrange.py#L250-L270)
- **Lines**:
  ```python
  # Line 250 (with_ties=True):
  ranks = df.groupby(by_cols, observed=False)[clean_col].rank(
      method="min", ascending=ascending, na_option="bottom" if na_last else "top"
  )
  filtered = df[ranks <= n]

  # Line 269 (with_ties=False):
  res = sorted_df.groupby(by_cols, as_index=False, observed=False, sort=False).head(n)
  ```
- **The Issue**:
  In standard Pandas, `df.groupby(..., dropna=True)` is the default. Because `dropna=False` is not passed to either `df.groupby()` invocation, any rows where `by_cols` contains `NaN` or `None` are **silently dropped from the output**.
  This directly contradicts Pytae's non-destructive data retention design (`dropna=False` by default in `agg`, `mutate(by=...)`, and `pivot`).
- **Reproduction**:
  ```python
  import pandas as pd
  import pytae as pt

  df = pd.DataFrame({
      "g": ["A", "A", None, None],
      "v": [10, 20, 30, 40]
  })

  print(pt.slice_max(df, "v", n=1, by="g"))
  # Observed Output:
  #    g   v
  # 0  A  20
  # Notice: rows where g=NaN were completely and silently discarded!
  ```
- **Expected Behavior**:
  Rows with `g=NaN` should form their own group and return the top row `(NaN, 40)`:
  ```text
       g   v
  0    A  20
  1  NaN  40
  ```
- **Recommended Fix**:
  Add `dropna=False` to both `groupby` calls in `_slice_ordered`:
  ```python
  # with_ties:
  ranks = df.groupby(by_cols, observed=False, dropna=False)[clean_col].rank(...)

  # without ties:
  res = sorted_df.groupby(by_cols, as_index=False, observed=False, sort=False, dropna=False).head(n)
  ```

---

### 1.2 [MEDIUM SEVERITY] `wide()` Crashes with `KeyError: None` on Modern Pandas When `v=None`

- **Location**: [`src/pytae/shape.py`](../src/pytae/shape.py#L202)
- **Lines**:
  ```python
  # Line 202:
  pivoted = df.pivot(index=index_cols, columns=c, values=v)
  ```
- **The Issue**:
  In Pandas 2.2+, calling `df.pivot(..., values=None)` causes an internal `KeyError: None` during column indexing inside `pandas/core/reshape/pivot.py`.
  Furthermore, `wide()`'s docstring lists `v: str = 'value'`, meaning that if `v` is omitted on a DataFrame lacking a column named `"value"`, it raises `KeyError: "wide(): values 'v' column 'value' not found in DataFrame"`.
- **Reproduction**:
  ```python
  import pandas as pd
  import pytae as pt

  df = pd.DataFrame({
      "id": [1, 2],
      "var": ["A", "B"],
      "val1": [10, 20],
      "val2": [100, 200]
  })

  pt.wide(df, c="var", v=None, index="id")
  # Raises: KeyError: None (inside pandas IndexEngine)
  ```
- **Recommended Fix**:
  If `v is None`, either pass all non-index, non-`c` columns as a list to `values`, or handle `values` explicitly to produce clean 1D flattened column headers.

---

### 1.3 [MEDIUM SEVERITY] `safe_reset_index` Not Exported at Package Root

- **Location**: [`src/pytae/__init__.py`](../src/pytae/__init__.py)
- **The Issue**:
  `reference/pytae_reference.txt` and `docs/library/other_utilities.ipynb` document `safe_reset_index` as a key utility. However, `src/pytae/__init__.py` does not import or export `safe_reset_index`.
- **Reproduction**:
  ```python
  import pytae as pt
  pt.safe_reset_index(df)
  # Raises: AttributeError: module 'pytae' has no attribute 'safe_reset_index'
  ```
- **Recommended Fix**:
  Add `safe_reset_index` to `from .other_utilities import ...` and `__all__` in `src/pytae/__init__.py`.

---

### 1.4 [LOW SEVERITY] Stale Error Messages Referencing Deprecated `agg_df` in `src/pytae/agg.py`

- **Location**: [`src/pytae/agg.py`](../src/pytae/agg.py#L63-L109)
- **Lines**:
  - Line 63: `raise ValueError("agg_df: cannot compute 'n'...")`
  - Line 69: `raise ValueError("agg_df: cannot compute 'n'...")`
  - Line 101: `raise ValueError(f"agg_df: output column name '{col}' collides...")`
  - Line 107: `raise ValueError(f"agg_df: output column name '{dups[0]}' is duplicated...")`
  - Line 109: `raise ValueError("agg_df: output column name 'n' collides...")`
- **The Issue**:
  `agg_df` was deprecated in favor of `agg`, but internal error strings in `_agg_df_list` still display the prefix `agg_df:`.
- **Recommended Fix**:
  Update error messages to `agg():` or `agg:` to preserve consistent naming across error outputs.

---

### 1.5 [LOW SEVERITY] `PtAccessor` Missing `to_clip` Method

- **Location**: [`src/pytae/accessor.py`](../src/pytae/accessor.py)
- **The Issue**:
  `to_clip` is monkey-patched onto `pd.DataFrame.to_clip` in `other_utilities.py`. However, it is not implemented on the `PtAccessor` class (`df.pt`). Chained pipelines like `df.pt.qry(...).pt.select(...).pt.to_clip()` fail with `AttributeError`.
- **Recommended Fix**:
  Add a delegate method on `PtAccessor`:
  ```python
  def to_clip(self) -> None:
      """Copy DataFrame to system clipboard (TSV, no index)."""
      return self._obj.to_clipboard(index=False)
  ```

---

## 2. Architectural Analysis & Design Consistency

### 2.1 Index Management
- **`qry()`**: Intentionally preserves original indices (does not call `reset_index()`). This enables indexing and masking operations that reference original row indices.
- **`arrange()`, `slice_max()`, `slice_min()`, `agg()`, `pivot()`, `wide()`, `long()`**: Consistently reset to standard `RangeIndex(0, 1, 2, ...)`.
- **Verdict**: Consistent and well-designed once `slice_max`/`slice_min` null handling is corrected.

### 2.2 Grouping & Window Transformations in `mutate()`
- `mutate(by=...)` handles `NaN` group keys non-destructively:
  - If `dropna=False` (default), groups with `NaN` compute group statistics (`mean`, `sum`, etc.) across `NaN` rows.
  - Broadcast window transformations align cleanly with original row order.
- **Verdict**: Robust implementation.

### 2.3 Evaluation Engine Security & Sandboxing in `mutate()` and `qry()`
- `qry()` parses expressions into AST or structural tokens (`ops`, `_parse_qry_string`), completely avoiding unrestricted `eval()`.
- `mutate()` first attempts `pandas.eval()`. If that fails (e.g. for helpers like `if_else`, `map`, `case_when`), it compiles the expression through Python's `eval()` using a restricted namespace (`_compile_fallback`).
- **Verdict**: Secure against unintended code execution while supporting rich syntactic helpers.
