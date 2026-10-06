# Pytae Test Suite & Coverage Review

This document provides a thorough audit of the test suite (`tests/`, 606 passed tests), code coverage metrics across modules, untested edge cases, and recommendations for new tests.

---

## 1. Code Coverage Summary

Measurement obtained via `pytest-cov` on Python 3.14:

| Module | Statements | Missed | Coverage | Priority for Testing |
|---|---|---|---|---|
| `src/pytae/arrange.py` | 113 | 35 | **69%** | **CRITICAL** (Core analytical verb) |
| `src/pytae/readers.py` | 439 | 125 | **72%** | MEDIUM (File format drivers) |
| `src/pytae/select.py` | 225 | 57 | **75%** | HIGH (Column selection & exclusion) |
| `src/pytae/agg.py` | 256 | 55 | **79%** | HIGH (Aggregation core) |
| `src/pytae/cli_parsing.py` | 529 | 101 | **81%** | MEDIUM (CLI parser branches) |
| `src/pytae/cli_run.py` | 754 | 132 | **82%** | MEDIUM (CLI runtime dispatch) |
| `src/pytae/qry.py` | 169 | 19 | **89%** | LOW (Well-covered) |
| `src/pytae/sql.py` | 78 | 8 | **90%** | LOW (Well-covered) |
| `src/pytae/mutate.py` | 416 | 40 | **90%** | LOW (Strong test suite) |
| `src/pytae/plotting.py` | 785 | 72 | **91%** | LOW (Plotting engine) |
| `src/pytae/cli_pipeline.py` | 293 | 27 | **91%** | LOW (Pipeline engine) |
| `src/pytae/accessor.py` | 89 | 7 | **92%** | HIGH (Public API surface) |
| `src/pytae/cli.py` | 281 | 20 | **93%** | LOW (CLI entry point) |
| `src/pytae/shape.py` | 256 | 15 | **94%** | LOW (Pivoting & reshaping) |
| `src/pytae/_text.py` | 59 | 2 | **97%** | LOW (Tokenizing utilities) |
| `src/pytae/other_utilities.py`| 146 | 2 | **99%** | LOW (Extensively tested) |
| **TOTAL** | **4,949** | **728** | **85%** | |

---

## 2. Missing Test Cases & Untested Branches

### 2.1 `src/pytae/arrange.py` (69% Coverage)
The `arrange.py` module was recently consolidated and has significant untested functionality:

1. **`slice_max` and `slice_min` with `with_ties=True`**:
   - `test_arrange_slice.py` never calls `with_ties=True`.
   - *Suggested test*: `test_slice_max_with_ties()` asserting that multiple tied records for the n-th value are preserved.
2. **`slice_max` and `slice_min` with `by` containing `NaN`**:
   - Never tested with missing grouping keys.
   - *Suggested test*: `test_slice_max_group_by_null_keys()` asserting that rows with `NaN` in grouping column(s) are preserved as a distinct group when `dropna=False`.
3. **`slice_max` and `slice_min` with `n <= 0`**:
   - Lines 232–233: `if n <= 0: return df.iloc[0:0].copy()`.
   - *Suggested test*: `test_slice_max_zero_or_negative_n()` asserting an empty DataFrame with the original schema is returned.
4. **`na_last=False` handling**:
   - Never tested in `arrange`, `slice_max`, or `slice_min`.
   - *Suggested test*: `test_arrange_na_last_false()` asserting `NaN` values appear first when `na_last=False`.
5. **Unknown column fuzzy suggestions**:
   - Lines 130–140 and lines 228–230 implement `difflib.get_close_matches` error messages.
   - *Suggested test*: `test_arrange_unknown_column_did_you_mean()` asserting `KeyError` contains `"did you mean"`.
6. **Sequence of boolean directions in `arrange`**:
   - Lines 78–82 support `ascending=[True, False]`.
   - *Suggested test*: `test_arrange_ascending_sequence()`.

---

### 2.2 `src/pytae/accessor.py` (Only 4 Tests in `tests/test_accessor.py`)
`tests/test_accessor.py` currently only exercises `df.pt.agg()` and `df.pt.select()`.

The following accessor methods are **completely untested** in `test_accessor.py`:
- `df.pt.qry(...)`
- `df.pt.mutate(...)`
- `df.pt.arrange(...)`
- `df.pt.slice_max(...)`
- `df.pt.slice_min(...)`
- `df.pt.long(...)`
- `df.pt.wide(...)`
- `df.pt.pivot(...)`
- `df.pt.sql(...)`
- `df.pt.cols(...)`
- `df.pt.glimpse(...)`
- `df.pt.clean_columns(...)`
- `df.pt.replace_values(...)`
- `df.pt.handle_missing(...)`

*Recommendation*: Add a comprehensive accessor test verifying end-to-end method chaining across all core verbs.

---

### 2.3 `src/pytae/cli_parse.py` (Stale Tests)
- `tests/test_cli_parse.py` line 8 tests `parse_sort_by` (which is a deprecated legacy parser helper).
- `parse_arrange` and `parse_slice_spec` (which power `-arrange` and `-slice_max/-slice_min`) have **zero direct unit tests** in `test_cli_parse.py`.

*Recommendation*:
- Add tests for `parse_arrange` verifying comma separation, bracketed spaced columns, and inline direction suffixes.
- Add tests for `parse_slice_spec` verifying `'col:3'`, `'col,3'`, `'col,n=3'`, and syntax error handling.

---

### 2.4 `src/pytae/select.py` (75% Coverage)
Untested branches in `select.py`:
1. **`exclude_dtype` conflict error**:
   - Line 83 raises `ValueError("exclude_dtype cannot be combined with other selection criteria")` — untested.
2. **Negative slice notation (`-col_a:col_b`)**:
   - Lines 115–125 handle slice ranges within exclusion specs.
3. **Invalid regex error handling**:
   - Line 303 catches `re.error` and raises `ValueError("invalid regex: ...")`.

---

### 2.5 `src/pytae/shape.py`
1. **`wide()` with `v=None` on multi-variable tables**:
   - Currently triggers `KeyError: None` on modern Pandas.
   - Needs a test asserting expected behavior or a clear explanatory exception.
2. **`pivot()` with all-null value columns**:
   - Test behavior when aggregated metric is entirely `NaN`.

---

## 3. Weak Test Patterns Identified

1. **Over-reliance on `exit_code == 0`**:
   - Several CLI tests in `test_cli_clean.py` and `test_cli_reshape.py` check only `assert exit_code == 0` without validating stdout content or structure.
2. **Monkeypatching `to_clipboard` without schema assertions**:
   - `test_qry_clip_copies_filtered_frame_without_output_op` verifies clipboard execution, but does not verify column dtypes or index settings when exported via `-o clip`.
3. **Testing deprecated legacy functions**:
   - `test_parse_sort_by_trailing_direction` verifies the deprecated `parse_sort_by` parser instead of the active `parse_arrange` parser.
