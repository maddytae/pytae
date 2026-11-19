# Pytae — Master Reference & Architecture Guide

`pytae` is a tabular data manipulation framework designed around practical lessons from modern data workflows:
- It uses the **multithreaded SIMD execution** of Polars,
- Adopts the **readable, functional grammar** of dplyr,
- And avoids the **index hierarchies, API redundancies, and silent data loss defaults** of legacy libraries.

Pytae provides a single, unified grammar across **Python library code** (`df.<verb>()`, `pt.<verb>(df)`), the **Interactive Terminal REPL** (`pytae`), and the **Unix Command Line** (`pytae <file> -<verb>`).

---

## The Core Philosophy: "One and Only One Obvious Way"

In Python, the Zen of Python famously asserts:
> *"There should be one-- and preferably only one --obvious way to do it."*

Yet for over a decade, tabular data engineering and data science have drifted far from this ideal:

- **Pandas** offers four to six competing ways to accomplish nearly every basic operation:
  - Row filtering can be done via boolean masks `df[df['a'] > 1]`, `.loc[...]`, `.iloc[...]`, or `.filter()` (whereas legacy `df.query()` has been strictly retired in Pytae).
  - Column derivations require choosing between bracket assignment `df['c'] = ...`, `.assign()`, `.apply()`, or `transform()`.
  - Index management demands constant, defensive ceremony: `.reset_index()`, `.set_index()`, `.rename_axis(None)`, and unpacking nested `MultiIndex` tuples after every aggregation.
  - Silent data loss traps abound: `df.groupby(..., dropna=True)` silently discards rows with missing group keys, while `df.dropna()` defaults to `how='any'`, wiping out valuable records missing even a single optional column.
- **dplyr (R / Tidyverse)** introduced an elegant functional pipeline, but porting its concepts to Python introduces severe friction:
  - Non-Standard Evaluation (NSE) creates quoting ambiguity and makes programmatic column passing cumbersome (requiring `{{ col }}`, `across()`, or `.data[[col]]`).
  - Grouping is stateful and "sticky": `group_by()` produces a persistent grouped data frame that silently alters downstream verbs until the user remembers to chain an explicit `ungroup()`.
  - Spelling ambiguity (British `summarise` vs. American `summarize`) introduces unnecessary cognitive overhead.
  - There is zero native parity with the Unix shell or command-line pipelines.
- **SAS (Statistical Analysis System)** has long served as the enterprise standard in clinical trials, banking, and government, but remains locked in disjoint legacy paradigms:
  - Analytics are fragmented across two distinct execution engines: the procedural row-by-row `DATA` step and `PROC SQL`, alongside dozens of specialized procedures (`PROC SORT`, `PROC MEANS`, `PROC FREQ`, `PROC TRANSPOSE`, `PROC COMPARE`).
  - Window calculations and lag/lead operations require manual sort steps followed by stateful row loops with `RETAIN`, `FIRST.`, and `LAST.` flags.
  - Merging datasets (`MERGE ... BY ...`) strictly requires all input datasets to be pre-sorted on disk by the merge keys, with failure to do so resulting in fatal runtime aborts.
  - Missing numeric values (`.`) are sorted internally as smaller than negative infinity ($-\infty$), creating a notorious bug where `IF score < 50` evaluates to true for missing records!
  - Execution relies on heavy batch runs (`.sas` scripts producing voluminous `.log` and `.lst` spool files) with no interactive shell composability.

### The 7 Pillars of Pytae's Philosophy

`pytae` resolves these pain points by establishing **"One and Only One Obvious Way"** as an absolute, non-negotiable architectural doctrine:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        THE 7 PILLARS OF PYTAE ARCHITECTURE                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. ONE CANONICAL VERB     │ Exactly one obvious verb per task: filter, mutate, arrange, │
│                           │ by, agg, distinct, head, tail, wide, long, pivot, join.     │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 2. ZERO SYNTAX AMBIGUITY  │ No competing shortcuts or dual APIs. Explicit 'desc' for   │
│                           │ sorting; explicit predicate strings for missing checks.    │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 3. DUAL-MODALITY PARITY   │ 100% grammar symmetry between Python library & terminal    │
│                           │ CLI: df.filter(...) in code == -filter "..." in shell.     │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 4. PURE FLAT STRUCTURES   │ No indexes, no MultiIndex traps. Every operation returns   │
│                           │ flat 1D columns with clean RangeIndex(0, 1, 2, ...).       │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 5. ZERO DATA LOSS         │ Non-destructive safe defaults: bare dropna() drops only   │
│                           │ 100% blank rows; agg/pivot retain NA groups.               │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 6. SINGLE-SHOT GROUPING   │ df.by(*cols) scopes only the immediate next verb and auto- │
│                           │ ungroups. Sticky groups are eliminated; ungroup is dead.   │
├───────────────────────────┼────────────────────────────────────────────────────────────┤
│ 7. 100% POLARS SIMD CORE  │ Multithreaded Rust SIMD vector execution under the hood,   │
│                           │ bypassing Python GIL bottlenecks with zero overhead.      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 30-Second Quickstart

### In Python:
```python
import pytae as pt

# Eager read or lazy scan
penguins = pt.read("penguins.parquet")

report = (
    penguins.filter("body_mass_g > 3500 & sex.is_not_null()")
    .mutate(
        body_mass_kg="body_mass_g / 1000",
        bill_ratio="bill_length_mm / bill_depth_mm",
        status="'verified'"
    )
    .by("species", "island")
    .agg(
        n="count()",
        avg_mass_kg="mean(body_mass_kg)",
        max_ratio="max(bill_ratio)"
    )
    .arrange("avg_mass_kg desc")
)

# Export results
report.to("summary.parquet")
```

### On the Command Line:
The exact same logic translates directly to the terminal:

```bash
pytae penguins.parquet \
  -filter "body_mass_g > 3500 and sex.is_not_null()" \
  -mutate "body_mass_kg = body_mass_g / 1000, bill_ratio = bill_length_mm / bill_depth_mm, status = 'verified'" \
  -by species,island \
  -agg "n = count(), avg_mass_kg = mean(body_mass_kg), max_ratio = max(bill_ratio)" \
  -arrange "avg_mass_kg desc" \
  -o summary.parquet
```

---

## Core Architectural & Design Principles

Pytae translates its core philosophy into five concrete architectural principles that govern how data is structured, scoped, transformed, and exported:

### 1. Single-Shot Scoped Grouping (Why `ungroup()` is Obsolete)

Grouping in Pytae is an execution modifier, not a persistent object state:
- In **Pandas**, `.groupby()` creates a lazy `DataFrameGroupBy` object that fractures the API, breaks standard method chaining, and forces hierarchical `MultiIndex` outputs upon aggregation.
- In **dplyr**, `group_by()` produces a "sticky" grouped table that silently alters the behavior of all downstream verbs until manually cleared with `ungroup()`.
- In **Pytae, grouping is strictly single-shot and auto-clearing**:
  - `df.by(*cols)` sets an active grouping scope for the *immediate next verb*.
  - `.mutate()` computes window and partition calculations by group, consumes the grouping context, and immediately returns a clean, ungrouped `DataFrame`.
  - `.head()` / `.tail()` slices rows per group (including extreme values after `.arrange()`) and returns an ungrouped `DataFrame`.
  - `.agg()` collapses rows per group and returns an ungrouped `DataFrame`.
  - Because grouping is never sticky, subsequent operations naturally evaluate at the whole-table scope without needing an `ungroup()` verb.

```python
# Multi-scope grouping in a single fluent pipeline:
(
    df
    .by("region").mutate(regional_avg="mean(sales)")
    .mutate(global_avg="mean(sales)")
    .by("dept").mutate(dept_avg="mean(sales)")
)
```

### 2. Pure Flat DataFrames (No Indexes, No MultiIndex Traps)

Tabular data consists of rows and named columns. Index hierarchies (`Index`, `MultiIndex`) in legacy tools introduce persistent cognitive overhead and defensive boilerplate (`.reset_index()`, `.set_index()`, tuple unpacking, `droplevel()`):
- In Pytae, every operation—including multi-key group-bys, cross-tabulations (`pivot`), unmelting (`wide`), and aggregations (`agg`)—always produces a flat 2D table with 1D string column names and a standard `RangeIndex(0, 1, 2, ...)`.
- Reshaping operations (`long`, `wide`, `pivot`) share a unified `rcva` grammar (`r=rows`, `c=columns`, `v=values`, `a=aggregation`) and guarantee pure flat outputs without nested tuple headers.
- Column headers remain predictable, directly queryable, and instantly serializable to Parquet, Arrow, CSV, or relational databases without intermediate cleanup.

### 3. Non-Destructive Safe Defaults (Zero Silent Data Loss)

A data framework should never silently discard information by default:
- **Missing Group Retention**: Group-by aggregations (`agg`) and cross-tabulations (`pivot`) default to `dropna=False`, preserving rows with missing group keys as explicit `null` groups rather than quietly dropping them from analysis.
- **Safe Row Dropping**: Bare `df.dropna()` defaults to dropping only 100% empty rows (where every column is missing). In legacy tools, `dropna()` defaults to dropping rows where *any* column is missing (`how='any'`), frequently discarding valuable records due to a single unpopulated optional field.

### 4. Uniform `null`: Arrow-Native Missing Value Architecture

Missing data handling has historically been fragmented:
- **Pandas** conflated missing values with floating-point non-finites (`np.nan`), creating a legacy where integer columns with missing values were forcibly cast to float, before introducing a disjoint nullable hierarchy (`pd.NA`, `np.nan`, `None`).
- **Polars** strictly separated Arrow `null` (missingness across all data types) from IEEE 754 `NaN` (floating-point arithmetic results), introducing duplicate APIs and subtle comparison traps.

Pytae establishes a single, uniform missing value architecture: **all missing values and floating-point non-finites (`null`, `None`, `np.nan`, `float('nan')`) are normalized uniformly to Arrow `null` upon ingestion and derivation.**

#### Architectural Rationale for Uniform `null`:
1. **Elimination of the IEEE 754 Comparison Trap**:
   In Polars, IEEE 754 floating-point numbers implement `total_cmp`, where `NaN > all numbers` (including $+\infty$). If `NaN` is preserved, an expression like `df.filter("score > 15")` silently evaluates to `True` for rows where `score` is `NaN`, unintentionally including non-finite values in the results. Under uniform `null`, `null > 15` evaluates to `null` and is dropped, eliminating this silent data corruption trap.
2. **"One and Only One Obvious Way"**:
   Retaining separate concepts for `null` and `NaN` led to duplicate APIs: `dropna()` vs. `dropna(nans=...)`, `fillna()` vs. `fill_nan()` vs. `fill_null()`, and `.is_null()` vs. `.is_nan()`. Users were constantly forced to wonder whether a missing cell was an unrecorded value or a float calculation artifact. Uniform `null` provides a single obvious verb for each operation: `.is_null()`, `.is_not_null()`, `.fillna()`, and `.dropna()`.
3. **Native Nullable Integers from Python Dictionaries**:
   In Python, missing numbers in lists often arrive as `np.nan` or `float('nan')` (e.g. `{"id": [1, np.nan, 3]}`). In pure Polars, constructing a DataFrame from this input fails with `TypeError`. Pre-normalizing `nan` to `None` in Pytae enables integer columns with missing values to naturally construct as native nullable `Int64` without type errors or forced float casts.
4. **Clean, Predictable Exports**:
   Exporting mixed `null` and `NaN` columns to Excel or CSV creates an inconsistent mess of empty cells, `#NUM!` errors, and literal `"NaN"` strings. Uniform `null` ensures that all missing data exports consistently as native blank spreadsheet cells or empty delimited fields.

### 5. Decoupled Compute & Presentation Engines

Pytae enforces a clean separation of concerns between high-throughput data processing and output rendering:
- **Compute in Polars, Visualize in Plotter**: High-performance transformations execute in the multithreaded SIMD Polars core; visualizations route through Pytae's native `Plotter` engine (`df.plot()`). Pytae strictly prohibits implicit in-plot aggregations, ensuring pipelines remain predictable, performant, and reproducible.
- **Adaptive Terminal & Pipeline Presentation**: In an interactive TTY, outputs display formatted ASCII/Unicode tables sized to terminal width; when piped into Unix tools (`grep`, `awk`), Pytae switches to clean delimited streams.
- 👉 **Interactive Plotting Notebook**: [notebooks/plotting/plotting.ipynb](notebooks/plotting/plotting.ipynb)

---

## The Pytae Architecture: "One Grammar, Two Modalities"

Whether you are writing a production Python service, conducting exploratory analysis in a Jupyter notebook, or processing massive data streams in a Unix terminal, Pytae uses identical concepts, expression syntax, and naming:

```
                               ┌────────────────────────┐
                               │      Source File       │
                               │ (.parquet, .csv, etc.) │
                               └───────────┬────────────┘
                                           │
                      ┌────────────────────┴────────────────────┐
                      ▼                                         ▼
            Python Library API                         Command Line (CLI)
          import pytae as pt                         $ pytae file.parquet
     df = pt.read("file.parquet")                              │
                      │                                       │
      df.filter("sales > 100")                        -filter "sales > 100"
        .mutate(tax="sales * 0.08")                   -mutate "tax = sales * 0.08"
        .by("region")                                 -by region
        .agg(total_rev="sum(sales)", n="count")       -agg "total_rev = sum(sales), n = count"
        .arrange("total_rev desc")                    -arrange "total_rev desc"
                      │                                       │
                      ▼                                       ▼
              In-Memory Result                          Stdout / Export
           Clean, flat DataFrame                      Table view, -o lake/
```

---

## Lazy Evaluation & Background Execution: The High-Performance Engine

One of Pytae's most powerful capabilities is its native, transparent support for **Lazy Evaluation** backed by Polars' query optimizer and streaming execution engine.

In traditional tools like Pandas, operations are strictly eager: reading a 50 GB CSV or Parquet file attempts to allocate 150+ GB of memory upfront, frequently resulting in fatal out-of-memory (`OOM`) crashes. In Pytae, switching from eager exploration to out-of-core, high-throughput production data pipelines requires changing a single function call: `pt.read` $\rightarrow$ `pt.scan`.

```
                 EAGER EXECUTION (pt.read)                   LAZY EXECUTION (pt.scan)
              ┌─────────────────────────────┐             ┌─────────────────────────────┐
              │    pt.read("file.ext")      │             │    pt.scan("file.ext")      │
              └──────────────┬──────────────┘             └──────────────┬──────────────┘
                             │ Reads entire file                         │ Builds unexecuted
                             ▼ into memory                               ▼ logical plan
              ┌─────────────────────────────┐             ┌─────────────────────────────┐
              │      pytae.DataFrame        │             │      pytae.DataFrame        │
              │   (in-memory pl.DataFrame)  │             │    (lazy pl.LazyFrame)      │
              └──────────────┬──────────────┘             └──────────────┬──────────────┘
                             │ Immediate execution                       │ Chained verbs build
                             ▼ per verb                                  ▼ query graph
              ┌─────────────────────────────┐             ┌─────────────────────────────┐
              │ .filter().mutate().agg()    │             │ .filter().mutate().agg()    │
              └──────────────┬──────────────┘             └──────────────┬──────────────┘
                             │                                           │
                             ▼                                           ▼ Rust Query Optimizer:
                      Eager In-Memory                             • Predicate Pushdown (filter)
                          Result                                  • Projection Pushdown (select)
                                                                  • Parallel Multithreaded SIMD
                                                                         │
                                                                         ▼
                                                          Automatic Background .collect()
                                                          or Explicit df.collect()
```

### 1. Eager vs. Lazy: Two Modes, One Identical Grammar

Every single verb in Pytae operates identically whether the underlying data is an eager `pl.DataFrame` or a lazy `pl.LazyFrame`:

```python
import pytae as pt

# 1. Eager: Immediately loads file into RAM
eager_df = pt.read("transactions.parquet")
print(eager_df.is_lazy)  # False

# 2. Lazy: Scans metadata only; zero rows loaded into RAM
lazy_df = pt.scan("transactions.parquet")
print(lazy_df.is_lazy)   # True

# Converting between modes
lazy_from_eager = eager_df.lazy()     # Convert eager -> lazy
eager_from_lazy = lazy_df.collect()   # Explicitly materialize lazy -> eager
```

### 2. The Optimizer: Predicate & Projection Pushdown

When running on a lazy DataFrame, Pytae defers execution until results are required. Polars' underlying Rust optimizer analyzes the entire computational graph and applies physical query optimizations:

1. **Predicate Pushdown (Filter Pushdown)**:
   - When you write `.filter("status == 'completed' & amount > 100")`, Pytae does not read all rows and filter in Python.
   - It pushes the filter criteria directly down into the file reader. For Parquet files, entire row groups are skipped at the disk level using Parquet block metadata and statistics, reading only matching rows into memory.
2. **Projection Pushdown (Column Selection)**:
   - When you write `.select("customer_id", "total_spend")`, Pytae reads **only those two columns** from storage. The remaining 50+ columns in the file are never touched, dramatically reducing disk I/O and memory bandwidth.
3. **Slice / Limit Pushdown**:
   - Calling `.head(10)` or `.arrange("sales desc").head(5)` avoids scanning the remainder of the file once the threshold is satisfied.

#### Inspecting the Execution Plan with `df.explain()`
You can inspect the exact physical and logical optimizations performed by Pytae using `.explain()`:

```python
plan = (
    pt.scan("sales.parquet")
    .filter("region == 'East' & sales > 500")
    .mutate(tax="sales * 0.08")
    .select("order_id", "sales", "tax")
    .explain()
)
print(plan)
```
```text
FAST_PROJECT: [order_id, sales, tax]
  SELECT [col("order_id"), col("sales"), col("sales") * 0.08 AS "tax"]
    FILTER: [(col("region") == "East") & (col("sales") > 500)]
      PARQUET SCAN sales.parquet
        PROJECT 2/18 COLUMNS: [order_id, sales, region]
        PREDICATE: [(col("region") == "East") & (col("sales") > 500)]
```

### 3. Automatic Background `collect()`: Zero-Friction Materialization

In many data frameworks (like Spark or pure Polars), forgetting to call `.collect()` leads to type mismatches, missing methods, or runtime crashes. **Pytae eliminates this friction with intelligent background collection**:

- **Direct-to-Disk Streaming Sinks**:
  - Calling `df.to("output.parquet")` or `df.to("output.csv")` on a lazy DataFrame does not require an explicit `.collect()` call. Pytae triggers streaming execution directly into the output file, keeping memory usage constant even for terabyte-scale datasets.
- **Hive Partitioned Lake Writes**:
  - Calling `df.to("lake_dir", partition_by=["year", "region"])` writes a clean, partitioned directory tree (`lake_dir/year=2025/region=US/*.parquet`) that can be read back instantly with `pt.read("lake_dir")` or `pt.scan("lake_dir")`.
- **Zero-Friction In-Memory Exports**:
  - Export seamlessly with `df.to("records")` (list of row dicts for FastAPI/REST APIs), `df.to("dict")` (column dict), `df.to("arrow")` (zero-copy `pyarrow.Table`), `df.to("pandas")`, `df.to("polars")`, or `df.to("clip")`.
- **Smart Shape & Count Queries**:
  - In Pandas, checking `len(df)` loads the entire table into memory.
  - In Pytae, calling `len(lazy_df)` or `lazy_df.shape` executes a lightweight `select(pl.len()).collect().item()` query in the background, returning row and column counts in milliseconds without loading data records into RAM.
- **Non-Destructive Inspection (`glimpse`, `freq`, `hist`)**:
  - Calling `lazy_df.glimpse()` automatically pushes a `.limit(25)` scan in the background, allowing you to preview schemas and sample rows of multi-gigabyte datasets without materializing them into memory.
- **CLI Streaming & Auto-TTY Collection**:
  - The `pytae` command-line tool automatically builds a lazy query plan across input flags (`-filter`, `-mutate`, `-by`, `-agg`, `-arrange`) and executes it in background Rust code right at the terminal output boundary.

---

## Ecosystem Comparisons & Migration Guides

Pytae was designed to synthesize the best strengths of the modern data engineering landscape while eliminating historical baggage, index traps, and syntax fragmentation.

### High-Level Ecosystem Comparison Matrix

| Capability / Paradigm | Pandas | dplyr (R) | SAS | Pytae |
|:---|:---|:---|:---|:---|
| **Core Philosophy** | Multiple competing ways per task | Functional pipelines (`%>%`, `\|>`) | Procedural `DATA` step + PROCs | **One and Only One Obvious Way** |
| **Execution Engine** | Single-threaded Python & NumPy | C++ (cpp11) / R interpreter | Procedural row-by-row PDV loop | **Multithreaded Rust SIMD (Polars)** |
| **Out-of-Core / Lazy Execution** | No native lazy engine (OOM on big files) | Limited (requires external `dbplyr`) | Sequential disk streaming | **Native `pt.scan()` with query pushdowns** |
| **Index Traps & MultiIndex** | Constant `.reset_index()` & nested tuples | Not applicable (R data frame) | Not applicable | **Pure flat 1D columns; zero MultiIndex** |
| **Grouping Scope** | Lazy `DataFrameGroupBy` object | "Sticky" `group_by()` (requires `ungroup`) | `BY` statement (requires prior `PROC SORT`) | **Single-shot `by()` (auto-clearing)** |
| **Missing Data Retention** | `dropna=True` *(Drops missing groups!)* | Preserves `NA` groups by default | Drops missing groups unless `MISSING` | **`dropna=False` by default (Zero Data Loss)** |
| **Row-Dropping Default** | Bare `dropna()` drops if *any* col is NA | `tidyr::drop_na()` requires explicit cols | Custom `IF` filter | **Bare `dropna()` drops only 100% blank rows** |
| **Missing Value Sorting** | Nulls sorted at end (or start) | NAs sorted at end | **Missing `.` sorted as $< -\infty$ *(Bug trap!)* ** | **Safe Polars sorting (`nulls_last`)** |
| **Relational Joins** | `pd.merge()` / `df.join()` | `left_join()`, `inner_join()` | `MERGE` *(Fatal abort if unsorted on disk!)* | **`df.join()` (Instant in-memory hash join)** |
| **Reshaping Model** | `melt()`, `pivot()`, `pivot_table()` | `pivot_longer()`, `pivot_wider()` | `PROC TRANSPOSE` (`_NAME_`, `COL1`) | **Symmetric `long()`, `wide()`, `pivot()`** |
| **CLI / Shell Parity** | None (requires writing `.py` script) | None (requires `Rscript -e '...'`) | Batch `sas -sysin` (produces `.log`/`.lst`) | **100% grammar parity (`pytae -verb`)** |

---

### Dedicated Deep Dive Guides

For exhaustive syntax mappings, feature-by-feature Rosetta stones, and migration walkthroughs, see the dedicated guides:

- **[Pytae vs. Pandas Deep Dive & Rosetta Stone](comparisons/comparison_to_pandas.md)**:
  - Eliminating the `MultiIndex` nightmare and index management overhead.
  - Avoiding Pandas silent data loss traps (`dropna=True` in groupby).
  - Performance benchmarks: single-threaded Python GIL vs. native Polars Rust SIMD.
  - Complete 14-task syntax translation table and end-to-end pipeline comparison.

- **[Pytae vs. dplyr (R / Tidyverse) Deep Dive & Rosetta Stone](comparisons/comparison_to_dplyr.md)**:
  - Bringing Tidyverse elegance to Python without Non-Standard Evaluation (NSE) quoting headaches.
  - Why `ungroup()` is obsolete: comparing dplyr's sticky grouping with Pytae's single-shot auto-clearing `df.by()`.
  - Multi-column transformations: `across()` vs. Pytae's concise `(a, b)_cm = _ * 10`.
  - Full Tidyverse-to-Pytae Rosetta stone and Unix CLI parity.

- **[Pytae vs. SAS Deep Dive & Migration Guide](comparisons/comparison_to_sas.md)**:
  - Transitioning from the procedural Program Data Vector (PDV) to modern vectorized SIMD execution.
  - The dangerous SAS missing value trap (numeric `.` sorting below negative infinity).
  - Eliminating the mandatory pre-sorting requirement of SAS `MERGE ... BY ...`.
  - Clinical trial analysis walkthrough (SDTM `VSL` & `DM`) and native `.sas7bdat` file ingestion.

---

## Detailed Documentation Directory

All comprehensive guides, API signatures, CLI flags, walkthroughs, and edge cases are documented under **`docs/`**:
- **`docs/cli_cheatsheet.md`**: [**The Definitive CLI Cheat Sheet & Cookbook**](cli_cheatsheet.md) — 12 curated sections of one-liner recipes and Unix shell workflows.
- **`docs/guides/`**: Comprehensive Feature & Command Line Markdown guides (`.md`)
- **`docs/notebooks/`**: Interactive, fully executed Jupyter Companion Notebooks (`.ipynb`)
- **`docs/ipython.md`**: [**IPython & Jupyter Workbench Guide**](ipython.md) — auto-activated magics, checkpoints, `%free`, `%set`, and `%export`.
- **`docs/comparisons/`**: Deep dive migration guides and Rosetta Stones.

| Category | Python Library (Notebook) | CLI & Engine Guide (Markdown) | Key Capabilities & Verbs |
|:---|:---|:---|:---|
| **Data I/O** | **[read_write.ipynb](notebooks/library/read_write.ipynb)** | **[read_write.md](guides/read_write.md)** | `pt.read`, `pt.scan`, `df.to`, `pt.to`, `-o`, `-out_dir`, `-fmt`, `-progress`, STDIN, clipboard |
| **Derivations** | **[mutate.ipynb](notebooks/library/mutate.ipynb)** | **[mutate.md](guides/mutate.md)** | `mutate`, formulas, sequential assignments, `if_else`, `case_when`, `map`, `shift`, `@var` |
| **Row Filtering** | **[filter.ipynb](notebooks/library/filter.ipynb)** | **[filter.md](guides/filter.md)** | `filter`, `assert_` (data assertions), intervals `[10, 20]`, set membership `in`, `or`/`and`, string methods, callables |
| **Columns** | **[select.ipynb](notebooks/library/select.ipynb)** | **[select.md](guides/select.md)** | `select`, drop with `!`, regex/patterns, inline rename, `pt.everything` |
| **Sorting** | **[arrange.ipynb](notebooks/library/arrange.ipynb)** | **[arrange.md](guides/arrange.md)** | `arrange`, ascending, descending `col desc`, multi-column ordering, null positioning |
| **Aggregation** | **[agg.ipynb](notebooks/library/agg.ipynb)** | **[agg.md](guides/agg.md)** | `by`, `agg`, `n`, `mean`, `sum`, `std`, `median`, `min`, `max`, `dropna=False` Zero Data Loss |
| **Cross-Tab** | **[pivot.ipynb](notebooks/library/pivot.ipynb)** | **[pivot.md](guides/pivot.md)** | `pivot`, `r=`, `c=`, `v=`, `a=`, `f_v=`, flat 1D columns (no MultiIndex traps) |
| **Deduplication** | **[distinct.ipynb](notebooks/library/distinct.ipynb)** | **[distinct.md](guides/distinct.md)** | `distinct`, whole-table deduplication, subset uniqueness, `keep='first'\|'last'\|'none'` |
| **Slicing** | **[head_tail.ipynb](notebooks/library/head_tail.ipynb)** | **[head_tail.md](guides/head_tail.md)** | `arrange` + `head`/`tail`, group-aware with `by`, percentage `prop=`, ties `with_ties=` |
| **Reshaping** | **[reshape.ipynb](notebooks/library/reshape.ipynb)** | **[reshape.md](guides/reshape.md)** | `long` (unpivoting), `wide` (1:1 pivoting), and `explode` (unnesting list/array columns) |
| **Relational Joins**| **[join.ipynb](notebooks/library/join.ipynb)** | **[join.md](guides/join.md)** | `df.join`, `pt.join`, `pt.concat`, inner/left/right/full/semi/anti/cross, colon keys, `validate` |
| **Masking & Privacy**| **[other_utilities.ipynb](notebooks/library/other_utilities.ipynb)** | **[mask.md](guides/mask.md)** | `mask`, `unmask`, `-mask`, `-unmask`, SHA-256 hash, salt, redact, key encryption, vault tokenization |
| **IPython Workbench**| — | **[ipython.md](ipython.md)** | `import pytae as pt`, `%pt`/`%%pt`, `%checkpoint`, `%restore`, `%status`, `%free`, `%set`, `%export`, `%exit -s` |
| **Utilities** | **[other_utilities.ipynb](notebooks/library/other_utilities.ipynb)** | **[clean_replace.md](guides/clean_replace.md)**<br>**[diff.md](guides/diff.md)** | `fillna`, `dropna`, `clean_columns`, `diff` (key-aware with `on=`, `tol=`), `glimpse`, `cols`, `df.to("clip")` |
| **Inspection** | **[other_utilities.ipynb](notebooks/library/other_utilities.ipynb)** | **[inspect.md](guides/inspect.md)** | `-cols`, `-dtype`, `-shape`, `-nulls`, `-head`, `-tail`, `-glimpse`, `-summary`, `-freq`, `-hist`, `-bar`, `-scatter`, `-corr` |
| **Multi-File** | **[join.ipynb](notebooks/library/join.ipynb)** | **[multi_file.md](guides/multi_file.md)** | Multi-table pipelines (`alias=source`), multi-file globbing (`*.parquet`), multi-table joining, batch inputs, pipes, Unix redirection |
| **SQL Engine** | **[sql.ipynb](notebooks/library/sql.ipynb)** | **[sql.md](guides/sql.md)** | `df.sql()`, `pt.sql()`, `-sql` native Polars SQL engine (SQLContext) on data and files |
| **Plotting** | **[plotting.ipynb](notebooks/plotting/plotting.ipynb)** | **[cli_plots.md](guides/cli_plots.md)** | `df.plot()`, `-plot`, `-finalize`, terminal `-bar`, `-scatter`, `-corr`, headless figures |
| **Doc Search & MCP** | — | — | `pytae -doc <query>`, `pt.doc()`, `pytae -mcp` stdio JSON-RPC 2.0 server for Copilot/Cursor |
| **Comparisons** | **[vs. Pandas](comparisons/comparison_to_pandas.md)**<br>**[vs. dplyr](comparisons/comparison_to_dplyr.md)**<br>**[vs. SAS](comparisons/comparison_to_sas.md)** | — | Pytae vs. Pandas vs. dplyr vs. SAS, core architecture, "one and only one obvious way" |
| **Benchmarks** | **[benchmarks.ipynb](benchmarks/benchmarks.ipynb)** | **[run_benchmarks.py](benchmarks/run_benchmarks.py)**<br>**[README](benchmarks/README.md)** | Reproducible 5M-row speed benchmarks: Pytae vs. Pandas/dplyr/SAS, timings & plots |

---

## IPython & Jupyter Workbench (`import pytae as pt`)

Pytae's interactive workbench runs directly inside **IPython** and **Jupyter** (JupyterLab, VS Code Notebooks). Running `import pytae as pt` inside an active IPython/Jupyter session automatically activates all workbench magics, persistent display formatters, and context-aware Tab completion (outside IPython, IPython is never imported).

| Magic | Example | Description |
|:---|:---|:---|
| `%pt` / `%%pt` | `res = %pt df -filter "x > 1"` / `%%pt res` | Full in-process Pytae CLI pipelines (immutable by default; works on RAM DataFrames, disk paths, `clip`, and `-sql`) |
| `%checkpoint` | `%checkpoint raw`, `%checkpoint diff df raw`, `%checkpoint rm raw` | Ephemeral Arrow IPC snapshots on disk (0 MB RAM) |
| `%restore` | `%restore raw`, `%restore` | Strict DataFrame rollback + `Out`/`_` cache scrub + OS RSS trim |
| `%status` | `%status [-v]`, `%status df`, `%status checkpoint` | Tracked DataFrames, shapes, RAM, checkpoints, OS RSS, settings |
| `%free` | `%free big_df`, `%free *`, `%free` | Delete DataFrame(s), scrub hidden IPython `Out`/`_` refs & trim OS RSS |
| `%set` | `%set max_rows=20 comma=true`, `%set save` | Persistent display formatting (`~/.pytae/config.json`) |
| `%export` / `%exit -s` | `%export analysis.py`, `%export nb.ipynb`, `%exit -s out.py` | Export clean standalone `.py` or `.ipynb` with errored, rolled-back, and preview cells pruned |

👉 See the full guide in [**`docs/ipython.md`**](ipython.md).

