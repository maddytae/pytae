# `pytae` Repository Audit: "One Obvious Way" & Missing Features Review

**Date:** October 2026  
**Branch Reviewed:** `feature/full_polar`  
**Core Philosophy Evaluated:**  
> *"There should be one—and preferably only one—obvious way to do it."*  
> *"1:1 Vocabulary Parity between the Python Library (`pt` / `df`) and the Terminal CLI (`pytae`)."*

---

## Executive Summary

Following the migration to the native Polars AST engine, unified `lambda d:` custom functions in `mutate()`, and the consolidation of type casting into `mutate()`, `pytae` has a remarkably clean core grammar (`select`, `filter`, `mutate`, `agg`, `sort`, `distinct`, `join`, `pivot`, `melt`, `by`).

However, a full audit of `src/pytae/` and `docs/` reveals **8 areas of feature duplication** (mostly left over from earlier iterations or Pandas compatibility layers) and **7 high-value missing features / CLI-to-Library parity gaps**.

| Category | Count | Key Highlights |
| :--- | :---: | :--- |
| **Duplicate / Overlapping Features** | **8** | 5 ways to fill nulls (`fillna`, `fill_null`, `fill_nan`, `handle_missing`, `mutate`); 3 aliases for `dropna`; 2 ways to rename (`select` vs `rename`); 2 frequency flags (`-freq` vs `-value_counts`); 2 wide-reshape verbs (`wide` vs `pivot`). |
| **CLI ↔ Library Parity Bugs & Gaps** | **3** | `-fillna` is documented in `docs/detailed_docs/other_utilities.md` but missing in `cli.py`; `-sql` exists in CLI but `df.sql()` / `pt.sql()` is missing in Python; `pt.rename` is missing at top-level. |
| **Sorely Missed Analytical Features** | **4** | Date/time `.dt` accessors (`year`, `month`, `day`, `date()`); richer `.str` methods (`replace`, `slice`, `split`); rolling/diff window functions (`diff`, `pct_change`, `rolling_mean`, `row_number`); multi-column `sort` descending syntax parity. |
| **Legacy Pandas Holdovers** | **2** | Dead `src/pytae/mutate.py` shim; `freq()`, `hist()`, and `diff()` still convert to Pandas (`to_pandas()`) instead of using native Polars. |

---

## Part 1: Duplicate & Overlapping Features ("One Obvious Way" Audit)

### 1. Missing-Value Filling Has 5 Overlapping Entrypoints (`fillna`, `fill_null`, `fill_nan`, `handle_missing`, and `mutate`)
- **Where:**
  - `src/pytae/other_utilities.py` (`fillna`, `fill_null`, `fill_nan`, `handle_missing`)
  - `src/pytae/dataframe.py` (`DataFrame.fillna`, `DataFrame.fill_null`, `DataFrame.fill_nan`, `DataFrame.handle_missing`)
  - `src/pytae/polars_engine.py` (`col.fillna(0)`, `fillna(col, 0)`, `col.fill_null(0)`, `col.fill_nan(0)`, `coalesce(col, 0)` inside `mutate`)
  - `src/pytae/cli.py` (`-handle_missing`)
- **The Problem:**
  1. `df.fillna(val, *cols, nans=True)` already handles both `null` and `NaN` (controlled by `nans=True|False`), supports column subsets, and accepts a per-column dictionary (`df.fillna({"a": 0, "b": "unknown"})`). Having separate top-level `df.fill_null()`, `df.fill_nan()`, and `df.handle_missing()` verbs creates **4 separate DataFrame methods** for the same job.
  2. Worse, the CLI only implements `-handle_missing` (`numeric_fill,string_fill`) and **does not implement `-fillna`**, even though `docs/detailed_docs/other_utilities.md` (lines 15–17) explicitly documents `-fillna 0`, `-fill_null 0`, and `-fill_nan 0`!
- **Recommendation:**
  - **Keep ONE verb:** `fillna` (`df.fillna()`, `pt.fillna()`, CLI `-fillna`, and `fillna(x, 0)` inside `mutate`).
  - Support type-aware defaults in `fillna` (or `fillna(0, str="unknown")`) so `handle_missing`, `fill_null`, and `fill_nan` can be retired.

---

### 2. `dropna` Has 3 Identical Public Names (`dropna`, `drop_nulls`, `drop_na`)
- **Where:**
  - `src/pytae/__init__.py` (`__all__` exports all three: `dropna`, `drop_nulls`, `drop_na`)
  - `src/pytae/dataframe.py` (lines 727–747 & 1806–1824)
  - `src/pytae/accessor.py` (lines 118–138 & 380–399)
  - `src/pytae/cli.py` (line 216: `-dropna`, `-drop_nulls`, `-drop_na`)
- **The Problem:**
  - Elsewhere in `pytae`, aliases were intentionally removed to enforce *"one obvious way"* (e.g., `-unique` and `-dedupe` were removed in favor of `-distinct`; `-qry` was removed in favor of `-filter`).
  - Keeping 3 public names (`dropna`, `drop_nulls`, `drop_na`) across every class and CLI flag directly contradicts that standard.
- **Recommendation:**
  - **Keep `dropna`** (matches `fillna` and `isna` across `pytae`).
  - Remove `drop_nulls` and `drop_na` from `__all__`, `DataFrame`, accessors, and CLI flags (optionally raising a helpful hint on the CLI just like `-unique` → `"Use -distinct instead"`).

---

### 3. Column Renaming Has 2 Competing Mechanisms (`rename` vs `select`) with Different Syntax
- **Where:**
  - `df.select("a", new_b="b")` / CLI `-select "a, new_b=b"`
  - `df.rename({"b": "new_b"})` / `df.rename(b="new_b")` / CLI `-rename "b:new_b"` (`src/pytae/dataframe.py:1303`, `src/pytae/cli_pipeline.py:424`)
- **The Problem:**
  1. Notice the inverted direction and separator between the two:
     - In `select`: `new_name=old_name`
     - In `rename`: `old_name:new_name` (CLI) or `old_name="new_name"` (Python kwargs)
  2. `rename` is missing from top-level `pt.*` (`src/pytae/__init__.py`) and missing from `PolarsPtAccessor`, making it a partial verb.
- **Recommendation:**
  - Either make `rename` a first-class citizen with unified `new=old` (or `old:new`) syntax everywhere, **or** fold in-place renaming into `rename(new=old)` so it matches `select(new=old)` and `mutate(new=old)` without requiring users to remember whether `old` or `new` comes first.

---

### 4. Value Replacement Overlaps Between `replace_values` and `mutate` (`map` / `.str.replace`)
- **Where:**
  - `src/pytae/other_utilities.py:42` (`replace_values`)
  - `src/pytae/cli.py:210` (`-replace_values "v='M:Male', c=sex"`)
  - `src/pytae/polars_engine.py:725` (`mutate` `map(col, {'M': 'Male'})`)
- **The Problem:**
  - `replace_values` was created before `mutate` gained native `map(col, {...})` and across-column `(a, b) = ...` expressions.
  - Furthermore, `replace_values` uses a bespoke mini-language (`v='old:new;foo:bar', c='col1,col2'`) found nowhere else in `pytae`.
- **Recommendation:**
  - Consider whether `replace_values` is still needed if `mutate` supports `.str.replace()` and `map(col, {'M': 'Male'})` (with across syntax `(c1, c2) = map(_, {'M': 'Male'})`).

---

### 5. Two reshaping verbs for Wide Format: `wide` vs `pivot`
- **Where:**
  - `src/pytae/reshape.py` (`wide` at line 5, `pivot` at line 45)
  - `src/pytae/cli.py` (`-wide` and `-pivot`)
- **The Problem:**
  - `df.wide(r="id", c="var", v="val")` and `df.pivot(r="id", c="var", v="val", a="sum")` take the exact same `r`, `c`, `v` arguments; the only difference is that `wide` calls Polars `.pivot(..., aggregate_function=None)` while `pivot` defaults to `a="sum"` (`aggregate_function="sum"`).
  - Having two top-level verbs (`wide` and `pivot`) for wide reshaping when `long` was already consolidated into `melt` (note the CLI hint: `"-long has been removed. Use -melt instead"`) is inconsistent.
- **Recommendation:**
  - **Consolidate into `pivot`**: Allow `a=None` (or `a="first"` / auto-detect when no `a` is needed) in `pivot`, and retire `wide` with a helpful hint (`"-wide has been removed. Use -pivot instead"`), matching how `-long` was retired in favor of `-melt`.

---

### 6. CLI Frequency Inspection Has 2 Flags (`-freq` vs `-value_counts`)
- **Where:**
  - `src/pytae/cli.py:139` (`-freq`) and `src/pytae/cli.py:165` (`-value_counts`)
  - `src/pytae/cli_run.py:258` (`args.value_counts`) and `src/pytae/cli_run.py:322` (`args.freq`)
- **The Problem:**
  - `-freq` exists in both the Python library (`df.freq("col")`) and the CLI (`-freq col`), and outputs a rich frequency table (Count, `%`, Cumulative `%`, and ASCII bar).
  - `-value_counts` is a CLI-only leftover from Pandas that converts to Pandas (`df.to_pandas().value_counts()`) and has no `pt.value_counts()` counterpart in the library.
- **Recommendation:**
  - Remove `-value_counts` (with a redirect hint: `"Use -freq instead"`) so `-freq` / `df.freq()` is the single obvious way to inspect categorical distributions.

---

### 7. Schema & Metadata Inspection Has Overlapping CLI Flags (`-glimpse`, `-info`, `-dtype`, `-cols`)
- **Where:**
  - `src/pytae/cli.py`: `-glimpse`, `-info`, `-dtype`, `-cols`
  - `src/pytae/cli_run.py:217`: `-info` converts the entire Polars DataFrame to Pandas (`df.to_pandas().info()`) just to print column types and non-null counts!
- **The Problem:**
  - `-glimpse` already displays row count, column count, column names, `<dtype>`, and sample values natively via Polars.
  - `-info` forces an expensive full-dataset conversion to Pandas.
  - In the Python library, both `df.cols()` (method, sorted by default) and `df.columns` (property, unsorted) exist.
- **Recommendation:**
  - Retire `-info` (or alias it to `-glimpse` / enhance `-glimpse` to optionally show null counts) and eliminate the `to_pandas().info()` call.

---

### 8. Four Ways to Exclude Columns in `select`
- **Where:** `src/pytae/select.py`
- **The Problem:**
  - Column exclusion currently supports 4 syntaxes: `df.select("-col")`, `df.select("!col")`, `df.select("~col")`, and `df.select(exclude="col")`, plus `exclude_dtype=`.
- **Recommendation:**
  - Standardize on one prefix in docs/examples (e.g., `"-col"` or `"!col"`) and consider retiring `exclude=` / `exclude_dtype=` keyword arguments if prefix negation (`"-col"`, `"-numeric"`) covers 100% of cases.

---

## Part 2: Sorely Missed Features (Library, CLI & Parity Gaps)

### 1. Broken CLI Parity: `-fillna` Is Documented in Docs, But Missing in `cli.py`!
- **Severity:** High (Documentation / Code mismatch)
- **Details:**
  - `docs/detailed_docs/other_utilities.md` (lines 15–17 and 52–59) documents:
    ```bash
    pytae data.csv -fillna 0
    pytae data.csv -fillna "a:0,b:unknown"
    ```
  - However, running `pytae data.csv -fillna 0` fails with `unrecognized arguments: -fillna` because `src/pytae/cli.py` only defines `-handle_missing`!
- **Fix:** Implement `-fillna` in `src/pytae/cli.py` and `src/pytae/cli_pipeline.py` (supporting both scalar `-fillna 0` and column mapping `-fillna "a:0,b:unknown"`), and retire `-handle_missing`.

---

### 2. Missing `df.sql()` / `pt.sql()` in the Python Library (Currently CLI-Only `-sql`)
- **Severity:** High (1:1 CLI ↔ Library Parity Gap)
- **Details:**
  - On the CLI, `pytae data.parquet -sql "SELECT species, AVG(body_mass_g) FROM data GROUP BY species"` works out of the box via `pl.SQLContext`.
  - In Python, `df.sql(...)` and `pt.sql(...)` **do not exist** on `pytae.DataFrame`!
- **Proposed Syntax:**
  ```python
  df.sql("SELECT species, AVG(body_mass_g) AS avg_mass FROM data GROUP BY species")
  ```
  *(Registering `self._df` under both `"data"` and `"self"` in `pl.SQLContext` takes ~10 lines of code and achieves 100% parity with `-sql`.)*

---

### 3. Date / Datetime (`.dt`) Operations in `mutate()` and `filter()`
- **Severity:** High (Most common real-world tabular task currently missing from the expression engine)
- **Details:**
  - Right now, `src/pytae/polars_engine.py` supports `.str` methods (`lower`, `upper`, `len`, `strip`, `contains`, `startswith`, `endswith`), math functions, and type constructors (`int`, `float`, `str`, `bool`), but has **zero `.dt` / date-time support**.
  - Analysts working with time-series, transactions, logs, or financial datasets cannot extract year/month/day or parse dates inside `mutate` or `filter` without dropping into `lambda d:`.
- **Proposed Syntax in `mutate` & `filter`:**
  - **Constructors:** `date(col)` / `datetime(col)` (or `date(col, '%Y-%m-%d')`)
  - **`.dt` Accessors:**
    - `col.dt.year`, `col.dt.quarter`, `col.dt.month`, `col.dt.day`, `col.dt.weekday`
    - `col.dt.hour`, `col.dt.minute`, `col.dt.second`
    - `col.dt.truncate("1mo")` / `col.dt.strftime("%Y-%m")`
  - **Example:**
    ```python
    df.mutate(
        order_date="date(order_ts)",
        year="order_date.dt.year",
        month="order_date.dt.month",
    ).filter("year >= 2025 and month in (1, 2, 3)")
    ```

---

### 4. Essential `.str` Methods Missing in `mutate()`: `replace`, `slice`, `split`, `extract`
- **Severity:** Medium-High
- **Details:**
  - Currently `polars_engine.py` (lines 433–458) only supports 7 `.str` methods: `lower`, `upper`, `title`, `strip`, `len`, `contains`, `startswith`, `endswith`.
  - Common string cleaning tasks—like replacing substrings (`col.str.replace("-", "_")`), taking substrings (`col.str.slice(0, 4)`), or regex extraction (`col.str.extract(r"(\d+)")`)—Currently fail in `mutate`.
- **Proposed Additions to `polars_engine.py`:**
  - `col.str.replace(pattern, value)` (and `col.str.replace_all(pattern, value)`)
  - `col.str.slice(offset, length)`
  - `col.str.extract(pattern, group=1)`
  - `col.str.zfill(width)` / `col.str.pad_start(width, char)`

---

### 5. Time-Series & Window Functions in `mutate()`: `diff`, `pct_change`, `rolling_*`, `row_number`, `first`, `last`
- **Severity:** Medium-High
- **Details:**
  - `mutate` already supports `shift`/`lag`/`lead`, `rank`, and `cumsum`/`cumprod`/`cummin`/`cummax`.
  - However, several ubiquitous window operations are missing from `polars_engine.py`:
    1. **`diff(col, n=1)` and `pct_change(col, n=1)`**: First differences and percentage returns (especially inside `.by("ticker").mutate(ret="pct_change(price)")`).
    2. **Rolling window functions**: `rolling_mean(col, window)`, `rolling_sum(col, window)`, `rolling_std(col, window)`, `rolling_min(col, window)`, `rolling_max(col, window)`.
    3. **`row_number()` / `first(col)` / `last(col)` / `n_unique(col)`**: Note that `first`, `last`, and `n_unique` already work in `agg()`, so users naturally expect them to work as window functions inside `mutate()` (e.g., `df.by("id").mutate(initial_val="first(val)")`).

---

### 6. `explode` / Unnesting List Columns (or Splitting Delimited Strings into Rows)
- **Severity:** Medium
- **Details:**
  - Modern Parquet/JSON datasets frequently contain array/list columns or comma-separated tags that need to be expanded into rows.
  - Polars has a super-fast `.explode(*cols)`, and `pytae` currently has no verb or CLI flag (`-explode col`) for it.

---

### 7. Native Export Methods & CLI Output Formats (`.jsonl`, `.xlsx`, `.ipc`)
- **Severity:** Low-Medium
- **Details:**
  - `readers.py` reads CSV, Parquet, JSONL/NDJSON, Arrow/IPC/Feather, Excel (`.xlsx`), SAS (`.sas7bdat`), SQLite, and DuckDB.
  - However, `DataFrame` only defines `to_parquet()`, `to_csv()`, `to_clip()`, `to_pandas()`, and `to_polars()`.
  - Adding `to_ndjson()` (or `to_json()`), `to_excel()`, and `to_dicts()`—and supporting `.jsonl` / `.ipc` in CLI `-o output.jsonl`—rounds out the I/O symmetry.

---

## Part 3: Legacy Pandas Holdovers & Dead Code to Clean Up

1. **`src/pytae/mutate.py` (Dead Code)**:
   - This 20-line file (`_apply_callable_or_eval`) is a leftover from the old Pandas `df.eval()` engine. It is only referenced in one legacy fallback branch and can be completely removed.
2. **`_rewrite_fallback_col_refs` in `src/pytae/_parsing.py`**:
   - Leftover regex rewriter for Pandas `df.eval()` fallback that is no longer needed with the pure Polars expression engine.
3. **Unnecessary `.to_pandas()` Conversions in `src/pytae/dataframe.py` and `src/pytae/cli_run.py`**:
   - `DataFrame.freq()` (`dataframe.py:926`) converts to Pandas (`self.to_pandas()`) instead of using native Polars `value_counts()`.
   - `DataFrame.hist()` (`dataframe.py:1009`) converts to Pandas (`self.to_pandas()[col].dropna()`) instead of using the Polars Series directly.
   - `DataFrame.diff()` (`dataframe.py:1066`) converts both DataFrames to Pandas to compare schemas/rows.
   - `cli_run.py` (`-info` and `-value_counts`) converts to Pandas (`df.to_pandas()`).

---

## Recommended Action Plan (Prioritized)

### Phase 1: Fix Parity Bugs & Consolidate Duplicates ("One Obvious Way")
- [ ] **1. Unify Missing-Value Filling into `fillna`**:
  - Add `-fillna` to the CLI (fixing the broken documentation in `other_utilities.md`).
  - Remove `fill_null`, `fill_nan`, and `handle_missing` (with CLI redirect hint `-handle_missing` → `Use -fillna instead`).
- [ ] **2. Clean Up `dropna` Aliases**:
  - Keep `dropna` (`df.dropna`, `pt.dropna`, `-dropna`); remove `drop_nulls` and `drop_na` aliases.
- [ ] **3. Clean Up CLI Inspection & Reshape Duplicates**:
  - Remove `-value_counts` in favor of `-freq`.
  - Remove `-info` (or alias to native Polars `-glimpse` without converting to Pandas).
  - Consolidate `wide` into `pivot` (or allow `pivot` with `a=None`).
- [ ] **4. Unify `rename` vs `select`**:
  - Decide whether to keep `rename` (with unified syntax and top-level `pt.rename` export) or fold renaming into `select` / `mutate`.

### Phase 2: High-Impact Missing Features
- [ ] **5. Add `df.sql()` / `pt.sql()`** to match CLI `-sql`.
- [ ] **6. Add `.dt` Date/Datetime Support in `mutate` & `filter`** (`date()`, `datetime()`, `.dt.year`, `.dt.month`, `.dt.day`, `.dt.weekday`, etc.).
- [ ] **7. Expand `.str` Methods in `mutate` & `filter`** (`.str.replace()`, `.str.slice()`, `.str.extract()`).
- [ ] **8. Add Window / Time-Series Functions in `mutate`** (`diff()`, `pct_change()`, `rolling_mean()`, `rolling_sum()`, `rolling_std()`, `first()`, `last()`, `row_number()`).

### Phase 3: Pure Polars Cleanup
- [ ] **9. Delete Dead Pandas Shims** (`src/pytae/mutate.py`, `_rewrite_fallback_col_refs`) and rewrite `df.freq()` / `df.hist()` to use native Polars without `self.to_pandas()`.

