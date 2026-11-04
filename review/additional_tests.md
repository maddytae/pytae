# Test Coverage Analysis & Additional Tests Plan

## 1. Per-Module Statement Coverage Summary

Line-by-line execution tracking (`sys.monitoring` across all **888 passing tests**) shows **75.0% overall statement coverage** (`8,033 / 10,710` executable statements across 20 source files).

| Module (`src/pytae/`) | Executable Stmts | Covered Stmts | Missed Stmts | Coverage % | Priority |
|---|---:|---:|---:|---:|---|
| `cli_help.py` | 36 | 36 | 0 | **100.0%** | Low |
| `_text.py` | 57 | 55 | 2 | **96.5%** | Low |
| `plotting.py` | 741 | 667 | 74 | **90.0%** | Low |
| `cli.py` | 406 | 363 | 43 | **89.4%** | Low |
| `__init__.py` | 164 | 139 | 25 | **84.8%** | Medium |
| `_parsing.py` | 655 | 545 | 110 | **83.2%** | Medium |
| `cli_run.py` | 898 | 743 | 155 | **82.7%** | Medium |
| `mask.py` | 275 | 224 | 51 | **81.5%** | Medium |
| `polars_engine.py` | 1,532 | 1,154 | 378 | **75.3%** | High |
| `cli_pipeline.py` | 396 | 297 | 99 | **75.0%** | Medium |
| `other_utilities.py` | 579 | 433 | 146 | **74.8%** | Medium |
| `validation.py` | 255 | 187 | 68 | **73.3%** | High |
| `dataframe.py` | 830 | 598 | 232 | **72.0%** | High |
| `cli_parsing.py` | 728 | 518 | 210 | **71.2%** | Medium |
| `repl.py` | 2,226 | 1,496 | 730 | **67.2%** | High |
| `readers.py` | 568 | 372 | 196 | **65.5%** | High |
| `select.py` | 261 | 154 | 107 | **59.0%** | **Critical** |
| `accessor.py` | 96 | 52 | 44 | **54.2%** | **Critical** |
| `cheatsheet.py` | 2 | 0 | 2 | **0.0%** (subprocess only) | Low |
| `__main__.py` | 5 | 0 | 5 | **0.0%** (subprocess only) | Low |
| **Total** | **10,710** | **8,033** | **2,677** | **75.0%** | |

---

## 2. Flawed or Weak Existing Tests

1. **`tests/test_count.py:42-51` (`test_count_accessors`) Never Tests `PandasPtAccessor.count`**:
   - The test accepts the Pandas fixture `df`, creates `pl_df = pl.from_pandas(df)`, and asserts on `pl_df.pt.count("g")` and `pt_df.count("g")`, but **never calls `df.pt.count("g")`** on the Pandas DataFrame `df`.
2. **`tests/test_cli_parse.py` Tests Dead Code**:
   - Tests `parse_sort_by()` (`src/pytae/cli_parsing.py:203-216`), which is no longer called anywhere in `src/pytae/`.
3. **Fixture Shadowing in `tests/test_repl.py:26`**:
   - Redefines `sample_parquet` locally with a different schema (`id, name, score, group`) than `tests/conftest.py:16` (`a, b, c`).

---

## 3. Prioritized Additional Tests by Module

### Priority 1: `src/pytae/accessor.py` (54.2% -> Target 98%+)
Currently, 22 methods on `PolarsPtAccessor` and `PandasPtAccessor` are completely untested. Add `tests/test_accessors_complete.py` covering:
- **Both `pl.DataFrame.pt`, `pl.LazyFrame.pt`, and `pd.DataFrame.pt` for every verb**:
  - `dropna`, `fillna`, `diff`, `head`, `tail`, `sample`, `count`, `value_counts`, `rename`, `sql`
  - `pivot`, `long` (including `r=` parameter once fixed), `wide`
  - `clean_columns`, `mask`, `unmask`, `cols`, `glimpse` (verifying `glimpse().mutate(...)` chaining)
  - `freq`, `hist`, `bar`, `scatter`, `corr`
  - `pipe`, `join`, `concat`, `to_pandas`, `to_polars`, `safe_reset_index`, `plot`

---

### Priority 2: `src/pytae/select.py` (59.0% -> Target 92%+)
Add unit tests in `tests/test_select.py` for the uncovered branches:
- **Type-based selection (`_matches_dtype`, lines 51-130)**:
  - Selector tokens `"date"`, `"datetime"`, `"datetimetz"`, `"timedelta"`, `"duration"`, `"time"`, `"category"`, `"bool"`, `"str"`, `"object"`, `"int"`, `"float"`, `"number"` tested against both Polars dtypes (`pl.Date`, `pl.Datetime("us", "UTC")`, `pl.Duration`, `pl.Time`, `pl.Categorical`) and Pandas dtypes.
- **Negated slice ranges and patterns (`resolve_select_columns`, lines 183-315)**:
  - Negated column ranges: `"!col_a:col_c"` and `"-col_a:col_c"`.
  - Typo suggestion error path: selecting a misspelled column `"bll_length_mm"` asserts `KeyError` contains `"did you mean 'bill_length_mm'?"`.
  - Inverted slice bounds (`"col_c:col_a"` when `col_c` appears after `col_a`).
- **Direct `select()` calls on raw frames (lines 370-427)**:
  - Calling `from pytae.select import select` directly on `pl.DataFrame`, `pl.LazyFrame` (verifying no `PerformanceWarning`), and `pd.DataFrame` with `exclude=` and `drop=True/False`.

---

### Priority 3: `src/pytae/readers.py` (65.5% -> Target 88%+)
Add unit tests in `tests/test_readers.py` covering:
- **IPC / Arrow / Feather I/O (lines 1126-1231)**:
  - `pt.read_ipc()` and `pt.scan_ipc()` with `columns=`, `n_rows=`, and `.collect()`.
  - `df.to_ipc()` round-trip verification.
  - CLI/REPL `get_reader` and `write_dataframe` on `.ipc`, `.arrow`, and `.feather` files.
- **JSON & NDJSON readers (lines 1085-1124, 1234-1267)**:
  - `pt.read_json()`, `pt.read_ndjson()`, and `pt.scan_ndjson()`.
- **Excel & Database readers (lines 998-1082)**:
  - `pt.read_excel()` (using `tmp_path` or mocked engine) and `pt.read_database()` with a temporary in-memory `sqlite3` connection (`sqlite:///...`).
- **YAML Connection Profiles (lines 727-822)**:
  - `PYTAE_CONNECTIONS_PATH` environment variable pointing to a temporary `connections.yaml` file (`csv`, `parquet`, `txt`, and invalid type error paths).
- **`LazyFrame` sink paths in `write_dataframe` (lines 928-970)**:
  - Passing a `pl.LazyFrame` to `write_dataframe()` for `.parquet` (`sink_parquet`), `.csv` (`sink_csv`), `.tsv`, and `.ndjson` (`sink_ndjson`).

---

### Priority 4: `src/pytae/dataframe.py` (72.0% -> Target 90%+)
Add unit tests in `tests/test_dataframe_methods.py` covering:
- **Lazy `DataFrame` operations (`pt.scan_parquet(...)`)**:
  - `.equals()`, `.to_numpy()`, `.values`, `.iloc[0]`, `.iloc[0:2, 0:2]`, `.loc[...]`, `.select_dtypes()`, `._repr_html_()`.
  - Lazy export methods: `.to_parquet()`, `.to_csv()`, `.to_ipc()`, `.to_json()`, `.to_ndjson()`.
- **`GroupedDataFrame` edge cases (`lines 1365-1695`)**:
  - `df.group_by("g").head(prop=0.5, with_ties=True, by="val")` and `.tail(prop=0.5, with_ties=True, by="val")`.
  - `df.group_by("g").fillna({"val": 0})` and `df.group_by("g").dropna("val")`.
  - `df.group_by("g").count(sort=True, name="n")`.
- **Clipboard & Display helpers**:
  - `df.to_clip()` (with mocked `subprocess.Popen` to verify TSV/CSV payload without requiring a GUI clipboard).

---

### Priority 5: `src/pytae/repl.py` (67.2% -> Target 82%+)
Add tests in `tests/test_repl.py` covering:
- **Regression test for `-glimpse` and `<tbl> -glimpse`**:
  - Verify `session.execute_line("-glimpse", output_fn=captured.append)` passes the formatted glimpse string to `output_fn` (and does **not** pass a `DataFrame` object or double-print).
- **Shell escape and REPL piping (`execute_line`)**:
  - `!echo hello` shell escape execution.
  - `-cols | grep ...` shell pipe execution (`_run_with_shell_pipe`).
- **Multi-table session management**:
  - `tables`, `use <tbl>`, `drop <tbl>`, `rename_table <old> <new>`, `clear`, `reset`, `history`, `vars`, `del <var>`.
  - Error paths in `_cmd_load` (verifying error message is printed once, not twice), `_cmd_save` (unsupported extension), and `_cmd_join` (missing table / invalid join type).

---

### Priority 6: `src/pytae/validation.py` (73.3% -> Target 92%+)
Add tests in `tests/test_validation.py` covering:
- **`run_cli_check` and `check_dsl_paths` (lines 420-560)**:
  - Running `pytae check <file_or_dir>` on Python files containing valid and invalid Pytae DSL expressions (`df.filter(...)`, `df.mutate(...)`, `df.select(...)`, `df.agg(...)`).
  - `DSLDiagnostic.format(color=True)` and `DSLDiagnostic.format(color=False)`.
- **`validate_pipeline` input source variants (lines 80-165)**:
  - Passing `source` as a `dict[str, pl.DataType]`, `pl.Schema`, `pd.DataFrame`, `.csv`, `.parquet`, `.ipc`, and `.txt` file path.

---

### Priority 7: `src/pytae/polars_engine.py` (75.3% -> Target 88%+)
Add tests in `tests/test_polars_engine_edge_cases.py` covering:
- **String & DateTime namespace methods in `filter` and `mutate` (`_ast_to_polars_expr`, lines 920-1280)**:
  - `.str.strip()`, `.str.lstrip()`, `.str.rstrip()`, `.str.zfill()`, `.str.pad_start()`, `.str.pad_end()`, `.str.extract()`, `.str.count_matches()`, `.str.replace_all()`.
  - `.dt.year()`, `.dt.month()`, `.dt.day()`, `.dt.hour()`, `.dt.minute()`, `.dt.second()`, `.dt.weekday()`, `.dt.quarter()`, `.dt.strftime()`, `.dt.truncate()`, `.dt.epoch()`.
- **Cumulative & Window functions with `by=`**:
  - `cumsum`, `cumprod`, `cummin`, `cummax`, `rank`, `dense_rank`, `row_number`, `pct_change`, `ewm_mean`, `ewm_std` both ungrouped and grouped (`by="g"`).
- **`diff_polars` edge cases (lines 555-740)**:
  - Numeric tolerance (`tol=1e-3`) with `NaN` and `inf` values, schema mismatches (extra columns on left vs. right), and row-count differences when `on=` key is omitted vs. specified.

