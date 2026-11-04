# Repository Error & Bug Report

This document catalogs confirmed runtime bugs, crashes, type-checking issues, broken scripts, and invalid documentation examples discovered during a full-repository audit of `pytae`.

---

## 1. Runtime Bugs in Core Library (`src/pytae/`)

### 1.1 REPL `-glimpse` and `<table_name> -glimpse` Double-Print and Break Shell Piping
- **Location**:
  - `src/pytae/repl.py:1862` (`execute_line`)
  - `src/pytae/repl.py:2733` (`_cmd_targeted_pipeline`)
  - `src/pytae/dataframe.py:1244-1248` (`DataFrame.glimpse`)
- **Problem**:
  Both REPL inspection handlers execute:
  ```python
  output_fn(PytaeDataFrame(self.current_df).glimpse())
  ```
  However, `DataFrame.glimpse()` does **not** return a formatted string; it calls `print(format_glimpse(self._df))` directly to `sys.stdout` and returns `self` (`DataFrame`).
- **Impact**:
  1. The glimpse summary is printed directly to `sys.stdout` (bypassing `output_fn`, which breaks REPL shell pipes such as `-glimpse | grep ...` and output capture in tests).
  2. Immediately afterward, `output_fn` receives the returned `DataFrame` object and prints the entire table a second time after the glimpse output.
- **Recommended Fix**:
  Replace `output_fn(PytaeDataFrame(df).glimpse())` with `output_fn(format_glimpse(df))` in both `execute_line` (`src/pytae/repl.py:1862`) and `_cmd_targeted_pipeline` (`src/pytae/repl.py:2733`).

---

### 1.2 `validate_pipeline()` Crashes with `AttributeError` on Fallback File Extensions
- **Location**:
  - `src/pytae/validation.py:114`
  - `src/pytae/readers.py:1270-1271`
- **Problem**:
  In `validate_pipeline()`, when `source` is a file path whose suffix is not in `{".parquet", ".pq", ".csv", ".tsv", ".ndjson", ".jsonl", ".ipc", ".arrow"}` (for example `.feather`, `.txt`, `.dat`, `.xlsx`, `.json`, or `.sas7bdat`), line 114 falls back to:
  ```python
  df = read(source_str, **kwargs).head(0)
  ```
  However, `pytae.readers.read()` (`src/pytae/readers.py:1270-1271`) was retired and unconditionally raises:
  ```python
  AttributeError("pt.read() has been removed. Use specific readers like pt.read_csv(), pt.read_parquet(), pt.read_excel(), or pt.scan_parquet() instead.")
  ```
- **Impact**:
  `pt.validate_pipeline("data.txt", ...)` or `pt.validate_pipeline("data.xlsx", ...)` crashes with an unhandled `AttributeError`.
- **Recommended Fix**:
  Use `get_reader(Path(source_str), **kwargs).head(0)` (or dispatch to the appropriate `read_*` function) instead of calling the retired `read()` stub.

---

### 1.3 `.pt.glimpse()` Accessor Breaks Method Chaining on Polars and Pandas DataFrames
- **Location**:
  - `src/pytae/accessor.py:153-157` (`PolarsPtAccessor.glimpse`)
  - `src/pytae/accessor.py:394-398` (`PandasPtAccessor.glimpse`)
- **Problem**:
  `DataFrame.glimpse()` (`src/pytae/dataframe.py:1244-1248`) and `pt.glimpse()` (`src/pytae/__init__.py:303-305`) return a `pytae.DataFrame` so users can chain Pytae verbs after inspecting a pipeline (`df.glimpse().mutate(...)`).
  In contrast, `PolarsPtAccessor.glimpse()` returns `self._obj` (`pl.DataFrame | pl.LazyFrame`) and `PandasPtAccessor.glimpse()` returns `self._obj` (`pd.DataFrame`).
- **Impact**:
  Chaining `pl_df.pt.glimpse().filter("a > 1")` or `pd_df.pt.glimpse().mutate("b = a * 2")` raises `AttributeError` (or calls Pandas' native `.filter()` with incompatible semantics) whereas every other chainable `.pt.<verb>()` method returns a `pytae.DataFrame`.
- **Recommended Fix**:
  Delegate `glimpse()` on both accessors to `return DataFrame(self._obj).glimpse()`.

---

### 1.4 Lazy `DataFrame` (`pt.scan_*`) Crashes on `.equals()`, `.values`, `.to_numpy()`, and `.iloc`, and Emits `PerformanceWarning` on `.select_dtypes()` / `pt.select()`
- **Location**:
  - `src/pytae/dataframe.py:88, 95-110` (`_IlocIndexer.__getitem__`)
  - `src/pytae/dataframe.py:341-345` (`DataFrame.equals`)
  - `src/pytae/dataframe.py:350-355` (`DataFrame.values`, `DataFrame.to_numpy`)
  - `src/pytae/dataframe.py:364` (`DataFrame.select_dtypes`)
  - `src/pytae/select.py:380-381` (`select`)
- **Problem**:
  When a `pytae.DataFrame` wraps a `pl.LazyFrame` (e.g., from `pt.scan_parquet()`):
  1. `df.equals(other)` calls `self._df.equals(other._df)` (`dataframe.py:344`), which raises `AttributeError: 'LazyFrame' object has no attribute 'equals'`.
  2. `df.to_numpy()` and `df.values` call `self._df.to_numpy()` (`dataframe.py:352, 355`), which raises `AttributeError: 'LazyFrame' object has no attribute 'to_numpy'`.
  3. `df.iloc[0]` calls `self._df._df.row(key)` / `self._df._df.columns` (`dataframe.py:88, 100`), which raises `AttributeError: 'LazyFrame' object has no attribute 'row'`.
  4. `df.select_dtypes(...)` (`dataframe.py:364`) accesses `self._df.schema` directly instead of `self._get_schema()`, and `pt.select(lazy_pl_df, ...)` (`select.py:380-381`) accesses `df.columns` and `df.schema` directly on `pl.LazyFrame`, both triggering Polars `PerformanceWarning: Determining the column names/schema of a LazyFrame requires resolving its schema, which is a potentially expensive operation`.
- **Recommended Fix**:
  - In `equals`, `to_numpy`, and `_IlocIndexer`, materialize `pl.LazyFrame` via `.collect()` (or `self._ensure_collected()`) before invoking eager-only Polars methods.
  - In `DataFrame.select_dtypes`, replace `self._df.schema.items()` with `self._get_schema().items()`.
  - In `select.py:380-381`, use `schema = df.collect_schema()` for `pl.LazyFrame` and derive `all_cols = list(schema.names())`.

---

### 1.5 `pt.long()` and `.pt.long()` Reject the `r=` Row-Identifier Parameter
- **Location**:
  - `src/pytae/__init__.py:259-266` (`pt.long`)
  - `src/pytae/accessor.py:123-130` (`PolarsPtAccessor.long`)
  - `src/pytae/accessor.py:364-371` (`PandasPtAccessor.long`)
- **Problem**:
  `DataFrame.long()` (`src/pytae/dataframe.py:1146-1160`) and `long_polars()` (`src/pytae/polars_engine.py:1892-1900`) accept `r: str | Sequence[str] | None = None` as the row-identifier parameter (matching `wide(r=...)` and `pivot(r=...)`).
  However, `pt.long()`, `PolarsPtAccessor.long()`, and `PandasPtAccessor.long()` only accept `(cols=None, into="variable", val="value", *, by=None)` without `r` or `**kwargs`.
- **Impact**:
  Calling `pt.long(df, r="id", cols="a,b")` or `df.pt.long(r="id", cols="a,b")` raises:
  ```
  TypeError: long() got an unexpected keyword argument 'r'
  ```
- **Recommended Fix**:
  Add `r: str | Sequence[str] | None = None` to `pt.long()`, `PolarsPtAccessor.long()`, and `PandasPtAccessor.long()`, and forward `r=r` to `DataFrame(df).long(...)`.

---

### 1.6 CLI and REPL Fail on Arrow IPC / Feather Files (`.ipc`, `.arrow`, `.feather`)
- **Location**:
  - `src/pytae/readers.py:830-839` (`_READERS`)
  - `src/pytae/readers.py:904-917` (`_WRITABLE_SUFFIXES` and `write_dataframe`)
  - `src/pytae/cli_run.py:1313-1326` (`valid_formats` in `-o`)
  - `src/pytae/repl.py:2934` (`_cmd_save`)
- **Problem**:
  Although the Python API supports `pt.read_ipc()`, `pt.scan_ipc()`, and `df.to_ipc()` for `.ipc`, `.arrow`, and `.feather` files, the CLI/REPL reader registry (`_READERS`) and writer registry (`_WRITABLE_SUFFIXES`, `valid_formats`) omit these extensions.
- **Impact**:
  - `pytae data.ipc -head 5` raises `ValueError: unsupported file type '.ipc'`.
  - `pytae data.parquet -o data.ipc` or `pytae data.parquet -o ipc` fails because `.ipc` is missing from `_WRITABLE_SUFFIXES` and `valid_formats`.
  - In the REPL, `load data.ipc` and `-o data.ipc` fail with `unsupported file type '.ipc'`.
- **Recommended Fix**:
  Add an `IpcReader` (or register `.ipc`, `.arrow`, `.feather` in `_READERS` and `_WRITABLE_SUFFIXES` in `src/pytae/readers.py` and `valid_formats` in `src/pytae/cli_run.py`).

---

### 1.7 Duplicate Error Print in REPL `_cmd_load`
- **Location**: `src/pytae/repl.py:2882-2884`
- **Problem**:
  In `_cmd_load`, the exception handler prints the exact same error message twice:
  ```python
  except Exception as exc:
      output_fn(f"pytae: failed to load {p}: {exc}")
      output_fn(f"pytae: failed to load {p}: {exc}")
  ```
- **Impact**:
  Every failed `load` command in the REPL outputs duplicate error lines.
- **Recommended Fix**:
  Remove the duplicate `output_fn(...)` call on line 2884.

---

### 1.8 Chaining `-freq <col> -bar` in CLI Creates a Duplicate Bar Chart Column
- **Location**:
  - `src/pytae/cli_run.py:678-694` (`_process_path`)
  - `readme.md:402`
  - `docs/cli_cheatsheet.md:196`
- **Problem**:
  `-freq <col>` produces a 3-column table `[<col>, "Count", "Distribution"]` where `"Distribution"` already contains an inline Unicode bar chart plus percentage (`████████████ (44.2%)`).
  When `-bar` is chained after `-freq` (as advertised in `readme.md` and `docs/cli_cheatsheet.md`: `pytae data.parquet -freq species -bar`), `_compute_bar` appends a fourth `"Bar"` column containing a second identical Unicode bar chart next to `"Distribution"`.

---

## 2. Type-Checking Configuration & Static Analysis Errors

### 2.1 `pyproject.toml` Silently Disables `mypy` Across 18 of 19 Source Modules
- **Location**: `pyproject.toml:68-80`
- **Problem**:
  ```toml
  [[tool.mypy.overrides]]
  module = ["pytae.*"]
  ignore_errors = true
  ```
  In `mypy`, `module = ["pytae.*"]` matches every submodule inside `src/pytae/` (`pytae.dataframe`, `pytae.polars_engine`, `pytae.repl`, `pytae.cli`, etc.), leaving only `src/pytae/__init__.py` checked.
- **Impact**:
  Running `mypy` without `ignore_errors = true` (`uv run --active mypy --config-file /dev/null --ignore-missing-imports --check-untyped-defs --exclude src/pytae/plotting.py src/pytae`) surfaces **121 type errors across 10 files**, including:
  - `src/pytae/polars_engine.py` (62 errors: `pl.DataFrame | pl.LazyFrame` union attribute mismatches, `Series` passed where `IntoExpr` expected, incompatible default types)
  - `src/pytae/other_utilities.py` (18 errors)
  - `src/pytae/dataframe.py` (13 errors: `LazyFrame.equals`, `LazyFrame.to_numpy`, `LazyFrame.schema`, `LazyFrame.height`)
  - `src/pytae/repl.py` (11 errors)
  - `src/pytae/readers.py` (7 errors: `Path | None` passed to `Path`, `stdin.buffer` attribute typing)
  - `src/pytae/select.py` (5 errors: `LazyFrame.columns` / `LazyFrame.schema`)

---

## 3. Broken Scripts & Repository Hygiene Issues

### 3.1 `scripts/update_doc_outputs.py` Has Non-Functional `--check` Flag and Always Overwrites Reference File
- **Location**: `scripts/update_doc_outputs.py:39-155`
- **Problems**:
  1. `--check` is registered on `argparse` (line 118) but `args.check` is **never read** anywhere in `main()`.
  2. `--regen-ref` is defined with `action="store_true", default=True` (line 125), which makes `args.regen_ref` unconditionally `True`—even when running `python scripts/update_doc_outputs.py --check`.
  3. `format_table()` (lines 39-61) is dead code and never called.
  4. `audit_docs()` (line 97) has return type annotation `-> dict[Path, list[str]]` but actually returns `dict[Path, dict[str, int]]`.

---

### 3.2 Tracked Binary and Leftover Scratch Files in Repository
- **Locations**:
  - `extensions/vscode-pytae/pytae-3.11.0.vsix` (tracked in git; stale v3.11.0 binary package while extension is at v3.12.8)
  - `out.csv` (1-byte untracked scratch file at repo root)
  - `pytae-macos-arm64.spec` (untracked PyInstaller spec at repo root containing hardcoded `/Users/maddy/Documents/my_repos/pytae/...` local paths)

---

## 4. Broken Examples in Documentation (`docs/`)

Running the code snippets in `docs/` against the current `pytae` engine reveals several examples that raise exceptions:

1. **Retired `.notna()` / `.isna()` methods inside `filter()` (raises `ValueError`)**:
   Pytae's filter parser supports `.is_not_null()` and `.is_null()`, not `.notna()` / `.isna()`.
   - `docs/pytae.md:353, 377` (`"bill_length_mm.notna() and body_mass_g.notna()"`, `df.filter("val.notna()")`)
   - `docs/comparison_to_pandas.md:175, 338, 350`
   - `docs/comparison_to_dplyr.md:155, 293, 305`
   - `docs/comparison_to_sas.md:234`
   - `docs/detailed_docs/cli/cli_plots.md:238`
2. **Retired comma-separated filter conditions (raises `ValueError: Multiple conditions in filter must be joined with 'and' or 'or'`)**:
   - `docs/comparison_to_sas.md:87, 373, 399` (`-filter "age >= 65, status == 'Active'"`, `df.filter("sex == 'M', age >= 14")`)
3. **Non-existent `pt.read_sas()` function (raises `AttributeError: module 'pytae' has no attribute 'read_sas'`)**:
   - `docs/comparison_to_sas.md:218, 369, 370`
4. **Unrecognized `-clean` CLI flag (raises `pytae: error: unrecognized arguments: -clean`; should be `-clean_columns`)**:
   - `docs/detailed_docs/cli/clean_replace.md:48`
   - `docs/comparison_to_dplyr.md:242`
   - `docs/comparison_to_pandas.md:268`
5. **Rejected double-dash `--select` CLI flag in cheatsheet (raises `pytae: error: '--select' uses a double dash. Use single-dash '-select' instead`)**:
   - `src/pytae/cheatsheet.py:58-65`
   - `docs/cli_cheatsheet.md:127-145`
6. **Broken link in `docs/binary_distribution.md:92`**:
   - Uses `file:///.github/workflows/build_binaries.yml` instead of a relative repository path `../.github/workflows/build_binaries.yml`.

