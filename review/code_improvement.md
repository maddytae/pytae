# Codebase Reduction & Improvement Opportunities

The `src/pytae/` package currently comprises **20 Python modules totaling ~18,900 lines of code (10,710 executable statements)**. A thorough audit identified **~1,270 lines of production code** (and **~200 lines of test code**) that can be removed through deduplication, dead-code elimination, and class consolidation without losing any functionality.

## Summary of Estimated Line Savings

| # | Area / File | Strategy | Current LOC | Projected LOC | Estimated Savings |
|---|---|---|---:|---:|---:|
| 1 | `src/pytae/accessor.py` | Extract `_BasePtAccessor` shared by `PolarsPtAccessor` & `PandasPtAccessor` | 504 | ~75 | **~430 lines** |
| 2 | `src/pytae/repl.py` | Unify duplicate inspection blocks, `_cmd_assign` branches, and `_eval_pipeline_df` / `_cmd_pipeline` | 3,435 | ~3,175 | **~260 lines** |
| 3 | `src/pytae/readers.py` | Extract `_DelimitedReader` base class for `CsvReader` and `TxtReader` | 1,272 | ~1,130 | **~140 lines** |
| 4 | `src/pytae/repl.py` | Delete unreachable disk-IPC undo/redo snapshot code (`_capture_session_state_to_disk`) | — | — | **~110 lines** |
| 5 | `src/pytae/cli_parsing.py`, `cli_pipeline.py`, `polars_engine.py`, `dataframe.py` | Delete unused/retired functions (`parse_sort_by`, `parse_arrange`, `parse_pick_spec`, `parse_qry`, `parse_group_agg`, `apply_pick`, `pick_polars`, `_get_level_values`) | — | — | **~90 lines** |
| 6 | `src/pytae/other_utilities.py` | Remove Pandas glimpse loop, deduplicate `corr()` pairwise helper, remove duplicate wrapper functions | 1,060 | ~910 | **~150 lines** |
| 7 | `src/pytae/cli_run.py` & `dataframe.py` | Consolidate `_compute_freq/hist/bar/scatter/corr` wrappers and shared `_copy_to_clipboard` | — | — | **~70 lines** |
| 8 | `src/pytae/__init__.py` | Restrict `_VerbDescriptor` bindings to the 3 submodules that share names with verbs | 510 | ~465 | **~45 lines** |
| 9 | `tests/test_*.py` | Consolidate repeated `sample_df` / `sample_parquet` fixtures into `tests/conftest.py` | — | — | **~200 lines** |
| **Total** | | | | | **~1,495 lines** |

---

## 1. Consolidate `PolarsPtAccessor` and `PandasPtAccessor` (`src/pytae/accessor.py`) — Save ~430 Lines

- **Location**: `src/pytae/accessor.py:20-504`
- **Problem**:
  `PolarsPtAccessor` (lines 20-255, 236 lines) and `PandasPtAccessor` (lines 259-504, 246 lines) define **35 identical methods** (`select`, `filter`, `mutate`, `agg`, `sort`, `distinct`, `dropna`, `fillna`, `diff`, `head`, `tail`, `sample`, `count`, `value_counts`, `rename`, `sql`, `pivot`, `long`, `wide`, `group_by`, `groupby`, `clean_columns`, `mask`, `unmask`, `cols`, `glimpse`, `freq`, `hist`, `bar`, `scatter`, `corr`, `pipe`, `join`, `concat`, `to_clip`, `plot`) that each do:
  ```python
  return DataFrame(self._obj).<method>(...)
  ```
- **Solution**:
  Create a single `_BasePtAccessor` containing `__init__` and all 35 delegating methods. Have `PolarsPtAccessor(_BasePtAccessor)` and `PandasPtAccessor(_BasePtAccessor)` only override the 2–3 framework-specific conversion helpers (`to_pandas`, `to_polars`, `safe_reset_index`).
  ```python
  class _BasePtAccessor:
      def __init__(self, obj: Any) -> None:
          self._obj = obj

      def _df(self) -> DataFrame:
          return DataFrame(self._obj)
      # ... 35 shared methods defined once ...
  ```

---

## 2. Unify Duplicated Inspection, Assignment, and Pipeline Execution in `src/pytae/repl.py` — Save ~260 Lines

### 2.1 Fast-Path Inspections Duplicated in `execute_line` and `_cmd_targeted_pipeline` (~90 Lines)
- **Locations**:
  - `src/pytae/repl.py:1796-1889` (`execute_line` active-table inspection fast-path, 94 lines)
  - `src/pytae/repl.py:2694-2765` (`_cmd_targeted_pipeline` named-table inspection fast-path, 72 lines)
- **Problem**:
  Both blocks parse `-time`, dispatch `-shape`, `-cols`, `-dtype`, `-nulls`, `-glimpse`, `-describe`, `-head`, and `-tail`, and format the elapsed suffix identically.
- **Solution**:
  Extract `self._try_fast_inspection(df: pl.DataFrame, tokens: list[str], output_fn: Callable[[Any], None], *, label: str | None = None) -> bool` and call it from both `execute_line` and `_cmd_targeted_pipeline`.

### 2.2 Active-Table and Cross-Table Branches in `_cmd_assign` (~45 Lines)
- **Locations**:
  - `src/pytae/repl.py:2531-2573` (when `rhs` starts with `-`)
  - `src/pytae/repl.py:2586-2636` (when `rhs` starts with `<source_table> -...`)
- **Problem**:
  Both branches validate the token list, run `self._eval_pipeline_df(source_df, pipeline_tokens, output_fn)`, capture undo state, store `self.tables[target] = res_df`, update `self.current_df`, and print `f"{target}: {r} rows x {c} cols{time_suffix}"`.
- **Solution**:
  Resolve `(source_df, pipeline_tokens)` in 6 lines at the top of `_cmd_assign` and execute the shared assignment/undo/reporting body once.

### 2.3 `_eval_pipeline_df` and `_cmd_pipeline` Share ~120 Lines of CLI Spec Parsing (~125 Lines)
- **Locations**:
  - `src/pytae/repl.py:3033-3204` (`_eval_pipeline_df`, 172 lines)
  - `src/pytae/repl.py:3206-3395` (`_cmd_pipeline`, 190 lines)
- **Problem**:
  Both methods build the CLI parser, parse `tokens`, validate `extra`, resolve `rename_specs`, `select_specs`, `filter_specs`, `mutate_specs`, `sql_specs`, `join_specs`, `concat_specs`, compute `has_action` and `show_all`, and call `_process_path(...)`.
- **Solution**:
  Have `_cmd_pipeline` delegate its core execution to `_eval_pipeline_df` (or a shared `_run_parsed_pipeline` helper) and only layer on the REPL-specific post-processing (`-o` export, visualization rendering, checkpoint update).

---

## 3. Consolidate `CsvReader` and `TxtReader` (`src/pytae/readers.py`) — Save ~140 Lines

- **Locations**:
  - `src/pytae/readers.py:148-317` (`CsvReader`, 170 lines)
  - `src/pytae/readers.py:320-491` (`TxtReader`, 172 lines)
- **Problem**:
  `CsvReader` and `TxtReader` share identical implementations of `columns`, `nrows`, `dtypes`, `head`, `tail`, `iter_chunks`, `to_dataframe`, `to_polars`, and `to_polars_lazy`. They differ only in default `sep` (`","` vs. `"\t"`) and `TxtReader`'s multi-character/regex separator fallback in `_read`.
- **Solution**:
  Make `TxtReader` subclass `CsvReader` (or a shared `_DelimitedReader` base class) and override only `__init__` and multi-character separator handling.

---

## 4. Remove Unreachable Disk-IPC Undo/Redo Machinery (`src/pytae/repl.py`) — Save ~110 Lines

- **Locations**:
  - `src/pytae/repl.py:2142-2188` (`_capture_session_state_to_disk`, 47 lines)
  - `src/pytae/repl.py:2250-2281` (`state.get("type") == "disk_ipc"` branch in `_apply_session_state`, 32 lines)
  - `src/pytae/repl.py:2114-2116, 2124-2126, 2327-2329, 2353-2355, 2557-2559, 2619-2621, 2656-2658, 2869-2871, 2971-2973, 3003-3005, 3369-3371, 3405-3407` (12 cleanup loops checking `snap.get("type") == "disk_ipc"`)
- **Problem**:
  `_capture_session_state_to_disk` is never called anywhere in the codebase; all undo/redo snapshots use in-memory zero-copy Polars references via `_capture_session_state()`.
- **Solution**:
  Delete `_capture_session_state_to_disk`, the `"disk_ipc"` branch in `_apply_session_state`, and the 12 dead `shutil.rmtree` cleanup loops.

---

## 5. Delete Dead/Retired Functions Across Core Modules — Save ~90 Lines

Every function listed below has zero call sites in `src/pytae/`:

1. **`src/pytae/cli_parsing.py` (78 lines total)**:
   - `parse_sort_by` (lines 203-216, 14 lines) — superseded by `parse_sort_spec`
   - `parse_arrange` (lines 219-231, 13 lines) — retired `-arrange` verb
   - `parse_pick_spec` (lines 327-330, 4 lines) — retired `-pick` verb
   - `_split_qry_entries` (lines 484-497, 14 lines) and `parse_qry` (lines 509-511, 3 lines) — retired `-qry` verb (`_split_mutate_entries` can inline the loop directly)
   - `parse_group_agg` (lines 572-601, 30 lines) — superseded by `parse_agg`
2. **`src/pytae/cli_pipeline.py:332-333` (2 lines)**:
   - `apply_pick` — retired `-pick` verb
3. **`src/pytae/polars_engine.py:1886-1889` (4 lines)**:
   - `pick_polars` — retired `pick` verb
4. **`src/pytae/dataframe.py:74-77` (4 lines)**:
   - `ColumnNames._get_level_values` — unused internal helper

---

## 6. Deduplicate `src/pytae/other_utilities.py` — Save ~150 Lines

1. **Remove redundant Pandas branch in `format_glimpse` (`src/pytae/other_utilities.py:201-232`, ~35 lines)**:
   `format_glimpse` has a 30-line Polars loop (lines 168-197) followed by a 32-line Pandas loop (lines 201-232). Converting non-Polars inputs upfront with `df = _to_polars_frame(df)` allows deleting the entire Pandas branch.
2. **Extract `_pair_corr` helper in `corr()` (`src/pytae/other_utilities.py:928-1055`, ~40 lines)**:
   The 18-line pairwise Polars correlation calculation (`pldf.select(pl.corr(c1, c2, method=method))` + `math.isnan` handling) is copy-pasted 3 times inside `corr()` (lines 928-946, 976-994, 1038-1055).
3. **Remove duplicate verb wrappers (`src/pytae/other_utilities.py:43-47, 111-131, 235-252`, ~40 lines)**:
   `cols()`, `clean_columns()`, `glimpse()`, and `distinct()` in `other_utilities.py` are legacy Pandas-era wrappers superseded by `polars_engine.py` and `DataFrame`.
4. **Consolidate `_to_polars_frame` (`src/pytae/other_utilities.py:310-326`, ~15 lines)**:
   Import `_ensure_polars` from `polars_engine.py` instead of maintaining a separate converter.

---

## 7. Consolidate Visualization & Clipboard Helpers in `src/pytae/cli_run.py` and `src/pytae/dataframe.py` — Save ~70 Lines

1. **Shared `_copy_to_clipboard` (~15 lines)**:
   `_copy_to_clipboard` is implemented identically in `src/pytae/dataframe.py:38-50` and `src/pytae/cli_run.py:227-238`. Keep one copy in `_text.py` (or `other_utilities.py`) and import it in both places.
2. **Consolidate `_compute_freq`, `_compute_hist`, `_compute_bar`, `_compute_scatter`, `_compute_corr` (`src/pytae/cli_run.py:128-224`, ~55 lines)**:
   All 5 functions follow the exact same pattern: wrap `df` in `PytaeDataFrame(df)`, call the corresponding method (`.freq()`, `.hist()`, `.bar()`, `.scatter()`, `.corr()`), unwrap `._df`, and convert raises into `ValueError(f"-{verb} error: {exc}")`. A single 15-line `_run_viz_verb(df, verb, *args, **kwargs)` replaces all 5 functions (97 lines -> ~40 lines).

---

## 8. Simplify `_PytaeModule` Descriptor Table (`src/pytae/__init__.py`) — Save ~45 Lines

- **Location**: `src/pytae/__init__.py:431-492`
- **Problem**:
  `_PytaeModule` attaches 48 `_VerbDescriptor` instances to prevent `import pytae.<submodule>` from shadowing top-level `pt.<verb>` functions. However, only **3** submodules in `src/pytae/` share names with top-level functions: `select`, `mask`, and `repl`.
- **Solution**:
  Bind `_VerbDescriptor` only for `("select", "mask", "repl")` (or generate descriptors dynamically in a 3-line loop over `_SHADOWED_SUBMODULES = ("select", "mask", "repl")`), saving ~45 lines.

---

## 9. Consolidate Duplicate Test Fixtures Across `tests/` — Save ~200 Lines

- **Problem**:
  `tests/conftest.py` already provides shared `df`, `sample_parquet`, `sample_csv`, and `penguins_parquet` fixtures, yet 14 test files (`test_repl.py`, `test_cli_filter.py`, `test_cli_mutate.py`, `test_cli_select.py`, `test_cli_join.py`, `test_cli_agg.py`, `test_cli_clean.py`, `test_cli_inspect.py`, `test_cli_visualizations.py`, `test_cli_reshape.py`, `test_cli_sql.py`, `test_cli_window.py`, `test_cli_io.py`, `test_cli_misc.py`) redefine their own local `_write_parquet` / `sample_parquet` / `penguins_df` helpers.
- **Solution**:
  Move the common CLI/REPL dataset fixtures into `tests/conftest.py` and reuse them across the test suite.

