# Pytae — Master Reference & Architecture Guide

`pytae` is a modern, high-performance tabular data manipulation framework that provides a single, unified grammar across both **Python code** (`df.<verb>()`, `pt.<verb>(df)`) and the **Command Line** (`pytae <file> -<verb>`). Backed by a 100% native multithreaded SIMD Polars core, Pytae eliminates boilerplate, index headaches, and performance bottlenecks.

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
        n="count",
        avg_mass_kg="body_mass_kg:mean",
        max_ratio="bill_ratio:max"
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
  -agg "n = count, avg_mass_kg = body_mass_kg:mean, max_ratio = bill_ratio:max" \
  -arrange "avg_mass_kg desc" \
  -o summary.parquet
```

---

## Naming Rationale: Why `filter`, `distinct`, `by`, `arrange`, `agg`, `long`/`wide`?

Pytae carefully chooses concise, intention-revealing names that eliminate ambiguity, prevent keyword collisions, and adhere strictly to *"One and Only One Obvious Way"*:

### 1. `filter` instead of `query` or `qry`
- **Why `filter`?** `filter` is the canonical, intuitive verb across modern data science (R `dplyr`, SQL `FILTER`, Polars, Apache Spark). Calling it `filter` provides immediate familiarity and zero surprise.
- **Why not `df.query()`?** Pandas' native `df.query()` is string-only and passes expressions to `numexpr`, which chokes on Python functions and spaced columns. In contrast, `df.filter()` supports:
  - **Bare Callables & Lambdas**: `df.filter(lambda d: d['mass'] > 4000)` with full Python expressions and functions.
  - **Mathematical Intervals**: `df.filter(mass="[3000, 4500]")` or `df.filter(pct="(0, 100)")`.
  - **Set Membership & Operators**: lists `cat=['A', 'B']`, tuples `species=('startswith', ['Ad', 'Ge'])`.
  - **Bracketed Spaced Columns**: `df.filter("[bill length mm] > 40")` without ugly backtick escaping.
  - **Keyword & Dictionary Syntax**: `df.filter(status="active")` or `{"col": "> 5"}`.
- **CLI Alignment**: The CLI uses `-filter "expr"`. The legacy `-qry` has been deprecated in favor of canonical `-filter`.

### 2. `distinct` instead of `dedupe`, `unique`, or `drop_duplicates`
- **Why `distinct`?** `distinct` is the universally recognized keyword in SQL (`SELECT DISTINCT`) and dplyr (`distinct()`). It clearly describes returning unique, deduplicated rows.
- **Why not `unique`?** In Pandas, `.unique()` is a Series method returning a 1D NumPy array of scalar values, not a DataFrame. Using `unique` would conflate scalar distinct values with full-table row deduplication.
- **CLI Alignment**: The CLI uses `-distinct "species,island"`, with optional `keep=first|last|none` control.

### 3. `by` for Single-Shot Scoped Grouping (Why `ungroup` is Obsolete)
- **Why `by` over `groupby`?** In Pandas, `.groupby()` creates a lazy `DataFrameGroupBy` object that breaks standard DataFrame method chaining and forces multi-level index outputs upon aggregation.
- In R's `dplyr`, `group_by()` produces a sticky grouped data frame that persists across operations unless the user manually chains `%>% ungroup()`.
- **In Pytae, grouping is strictly single-shot and auto-clearing**:
  - `df.by(*cols)` sets an active grouping context for the *immediate next verb*.
  - `.mutate()` executes window calculations partitioned by group, consumes the grouping, and immediately returns a clean, ungrouped `DataFrame`.
  - `.head()` / `.tail()` slices rows (including extreme values after `.arrange()`) per group and returns an ungrouped `DataFrame`.
  - `.agg()` collapses per group and returns an ungrouped `DataFrame`.
  - Because grouping is never sticky, subsequent operations naturally evaluate at the whole-table scope without needing an `ungroup()` verb.
- **Fluent Re-Grouping**: You can seamlessly transition between group scopes and overall table scopes in one chain:
  ```python
  (
      df
      .by("region").mutate(reg_avg="mean(sales)")
      .mutate(overall_avg="mean(sales)")
      .by("product").mutate(prod_avg="mean(sales)")
  )
  ```
- **Strict `*args` Only**: `df.by("species", "island")` requires clean positional `*args`. Nested lists (`df.by(["species"])`) and `df.by(None)` are strictly rejected with clear error guidance.
- **Precedence**: If a second `.by()` is called before being consumed, it cleanly overwrites the previous grouping context.

### 4. `arrange` instead of `sort` or `sort_by`
- **Why not `sort`?** Python's built-in list has `.sort()`, and Pandas previously had `.sort()` (deprecated in favor of `.sort_values()`). In CLI flags, `-sort` is ambiguous (does it sort rows, columns, or files?).
- **Why not `sort_by`?** `arrange` is the canonical Tidyverse verb for row ordering. It cleanly conveys ordering rows without implying whether an index or values are being sorted. It supports explicit ascending/descending declarations (`col desc`), multi-column ordering, and bracketed column names `[col name] desc`. Prefixing columns with `-` is intentionally rejected to prevent ambiguity with hyphenated column names or negative numbers.

### 5. `agg` instead of `summarise` or `summarize`
- **Why not `summarise`?** In Python, `summarise` vs `summarize` introduces spelling ambiguity (British vs American English). Having both violates *"One and Only One Obvious Way"*.
- **Why `agg`?** `agg` is universally recognized in Pandas (`.agg()`). By elevating `agg` (`df.agg()` and CLI `-agg`), Pytae eliminates spelling confusion while providing declarative named aggregations (`avg_mass="body_mass_g:mean"`, `total="count"`).

### 6. `long` and `wide` instead of `melt`, `stack`, `unstack`, `pivot_wider`
- Pytae uses strictly complementary, intuitive English opposites:
  - **`long()`**: Turns wide tables into tall records using the unified `rcva` grammar (`r=` or `id_vars=`, `c=`, `v=`).
  - **`wide()`**: Pure 1-to-1 structural unmelting without aggregation (`r=`, `c=`, `v=`).
  - **`pivot()`**: 2D cross-tabulation aggregation matrices (`r=`, `c=`, `v=`, `a=`).
- All three verbs produce pure, flat 1D column headers with zero MultiIndex traps.

### 7. `count` for Fast Tallying & Intention-Revealing Aggregations
- **Why `count`?** Counting occurrences of categories or combinations of factors is the single most common exploratory data analysis operation. In Pandas, users are forced to choose between `.value_counts()` (which returns a 1D Series with index labels, breaking fluent chaining) or `.groupby('col').size().reset_index(name='n')`.
- **First-Class Verb**: Pytae introduces a dedicated `count()` verb across both Python (`df.count("species")`, `df.by("species").count()`) and the CLI (`-count species`, `-by species -count`).
- **Intuitive Defaults**: `count()` automatically sorts descending by count (`sort=True`) with output column `name="n"`. Pass `sort=False` to preserve original encounter order, or `name="total"` to rename the tally.
- **Natural Grammar in `agg()`**: Inside `agg()`, `count` (or `count()`) is the canonical counting function (`total_penguins="count"`, `avg_mass="body_mass_g:mean"`). In `avg_mass="body_mass_g:mean"`, `mean` is the function; therefore, `total_penguins="count"` makes `count` the consistent, intention-revealing function name, eliminating the awkward `n="n"` parameter tautology while preserving `"n"` as an alias for backward compatibility.

### 8. Visualization: "Compute in Polars, Visualize with Pytae Plotter"
- **High-Performance Visualizer**: Polars delivers unmatched multithreaded SIMD vector speed for data ingestion, filtering, and aggregation. Visualizations are rendered via Pytae's native `Plotter` engine (`pytae.plotting.Plotter`), offering full integration with Matplotlib and Seaborn.
- **Zero-Friction Bridge**: Calling `.plot()` routes directly through `Plotter`. Users get multi-panel facet grids (`col`, `ncols`, `facet=True`), subplot mosaics (`mosaic="..."`), secondary axes (`^`), automatic legend consolidation, and publication themes, with seamless `.finalize().save('out.png')` chaining without writing conversion boilerplate.
- **Clean Separation of Concerns**: Aggregation belongs in Polars (`.by().agg()`); visualization belongs in Plotter (`.plot()`). Pytae strictly prohibits implicit in-plot aggregation, keeping your pipelines predictable and high-performance.
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
- **`docs/repl/`**: Deep dive guides for the interactive REPL shell and memory management.
- **`docs/comparisons/`**: Deep dive migration guides and Rosetta Stones.

| Category | Python Library (Notebook) | CLI & Engine Guide (Markdown) | Key Capabilities & Verbs |
|:---|:---|:---|:---|
| **Data I/O** | **[read_write.ipynb](notebooks/library/read_write.ipynb)** | **[read_write.md](guides/read_write.md)** | `pt.read_*`, `pt.scan_*`, `write_*`, `-o`, `-out_dir`, `-fmt`, `-progress`, STDIN, clipboard |
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
| **Interactive REPL**| — | **[repl/](repl/README.md)** | `pytae -i`, in-memory workbench, ephemeral Python sandboxing, `.to_pytae()`, `checkpoint`, `restore`, `rm table`, `exit -s` |
| **Utilities** | **[other_utilities.ipynb](notebooks/library/other_utilities.ipynb)** | **[clean_replace.md](guides/clean_replace.md)**<br>**[diff.md](guides/diff.md)** | `fillna`, `dropna`, `clean_columns`, `diff` (key-aware with `on=`, `tol=`), `glimpse`, `cols`, `to_clip` |
| **Inspection** | **[other_utilities.ipynb](notebooks/library/other_utilities.ipynb)** | **[inspect.md](guides/inspect.md)** | `-cols`, `-dtype`, `-shape`, `-nulls`, `-head`, `-tail`, `-glimpse`, `-summary`, `-freq`, `-hist`, `-bar`, `-scatter`, `-corr` |
| **Multi-File** | **[join.ipynb](notebooks/library/join.ipynb)** | **[multi_file.md](guides/multi_file.md)** | Multi-table pipelines (`alias=source`), multi-file globbing (`*.parquet`), multi-table joining, batch inputs, pipes, Unix redirection |
| **SQL Engine** | **[sql.ipynb](notebooks/library/sql.ipynb)** | **[sql.md](guides/sql.md)** | `df.sql()`, `pt.sql()`, `-sql` native Polars SQL engine (SQLContext) on data and files |
| **Plotting** | **[plotting.ipynb](notebooks/plotting/plotting.ipynb)** | **[cli_plots.md](guides/cli_plots.md)** | `df.plot()`, `-plot`, `-finalize`, terminal `-bar`, `-scatter`, `-corr`, headless figures |
| **Doc Search & MCP** | — | — | `pytae -doc <query>`, `pt.doc()`, `pytae -mcp` stdio JSON-RPC 2.0 server for Copilot/Cursor |
| **Comparisons** | **[vs. Pandas](comparisons/comparison_to_pandas.md)**<br>**[vs. dplyr](comparisons/comparison_to_dplyr.md)**<br>**[vs. SAS](comparisons/comparison_to_sas.md)** | — | Pytae vs. Pandas vs. dplyr vs. SAS, naming rationale, "one and only one obvious way" |
| **Benchmarks** | **[benchmarks.ipynb](benchmarks/benchmarks.ipynb)** | **[run_benchmarks.py](benchmarks/run_benchmarks.py)**<br>**[README](benchmarks/README.md)** | Reproducible 5M-row speed benchmarks: Pytae vs. Pandas/dplyr/SAS, timings & plots |
| **Benchmarks** | **[benchmarks.ipynb](benchmarks/benchmarks.ipynb)** | **[run_benchmarks.py](benchmarks/run_benchmarks.py)**<br>**[README](benchmarks/README.md)** | Reproducible 5M-row speed benchmarks: Pytae vs. Pandas/dplyr/SAS, timings & plots |

---

## Interactive REPL Shell (`pytae -i`)

The **Pytae REPL** provides stateful, iterative in-memory data manipulation and exploratory data analysis. In standard one-shot CLI usage, running multiple queries on a 1 GB file requires re-reading and re-parsing from disk every time. The Pytae REPL loads your dataset into RAM **once**, executing subsequent filters, aggregations, feature mutations, ANSI SQL queries, and Python logic at multithreaded Polars SIMD speeds.

### Core Architecture & Guarantees

1. **Dedicated Entrypoint (`pytae -i`)**: Interactive sessions launch cleanly with `pytae -i`. Datasets are loaded explicitly with `df = file.parquet`, guaranteeing that session logs and exported replay scripts are 100% reproducible and self-contained.
2. **Subject-First Multi-Table Workbench**: Load multiple datasets simultaneously (`df1`, `df2`, `orders`, `cust`). Run commands with clear prefixes (`df1 -head 5`, `orders -join cust on=id`), or switch active tables with `switch <name>` (`use` deprecated).
3. **Non-Destructive by Default**: Bare exploratory queries (`-pivot`, `-filter`, `-head`) format and display previews in the terminal without altering underlying tables in memory. State changes require explicit assignment (`df = df -filter ...`).
4. **Ephemeral Python Sandboxing & Persistent Logic**: Embedded Python execution (`py { ... }`) provides an extensibility escape hatch. Pre-loads `pd`, `pl`, `pt`, and `DataFrame`. Imported modules, custom functions, and classes persist throughout the REPL session, while transient scratch variables, arrays, and intermediate data objects are immediately purged from RAM upon block exit via `gc.collect()`. Only tables explicitly converted via `.to_pytae()` or assigned to `df` are registered in the workbench.
5. **Ephemeral IPC Checkpoints (0 MB RAM Overhead)**: Checkpoints serialize frozen table states to ephemeral Arrow IPC format on disk. They consume **0 MB of RAM** and are automatically purged upon session exit, allowing safe instant restoration via `restore [name]` or `reset`.

### Quick Reference of REPL Commands

| Category | Command | Example | Description |
|:---|:---|:---|:---|
| **Ingestion** | Assignment | `df = sales.parquet`<br>`cust = cust.csv -dlim ";"` | Ingest file into named table variable |
| **Workbench** | `status table` | `status table [-v]` | View loaded tables, shapes, memory, and columns |
| | `switch` | `switch cust` | Switch active dataset cursor (`use` deprecated) |
| | `rename` | `rename df1 customers` | Zero-copy $O(1)$ in-memory table pointer rename |
| | Subject-First | `cust -head 5`, `cust -shape` | Execute command directly on named table |
| | `rm table` | `rm table df1`, `rm table *` | Free table memory and trigger immediate OS page trim |
| **Transform** | Pipelines | `-filter "x > 1" -mutate "y = x * 2"` | Full 1:1 parity with Pytae CLI transformation flags |
| | Relational Joins | `orders -join cust on=id how=left` | Relational join across workbench tables |
| **Inspection** | Metadata | `-shape`, `-cols [asc\|desc\|pattern]`, `-schema`, `-nulls` | Non-destructive structural inspection |
| | Previews | `-head 10`, `-tail 5`, `-sample 10`, `-diff [target]` | Non-destructive formatted row previews & milestone diffs |
| **SQL & Python**| `-sql` | `-sql "SELECT * FROM orders JOIN cust ..."` | Pure ANSI SQL across all loaded workbench tables |
| | `py` | `py { k = df.to("pandas"); pt.DataFrame(k).to_pytae("k") }` | Embedded Python with persistent imports, ephemeral sandboxing & `.to_pytae()` |
| **Checkpoints** | `checkpoint` | `checkpoint baseline` | Save ephemeral IPC snapshot (0 MB RAM overhead) |
| | `restore` / `reset` | `restore baseline`, `reset` | Instantly revert workbench state to checkpoint |
| **Parameters** | `@var` | `min_val = 3500`, `@cfg.threshold` | Session variables substituted in `-filter`, `-mutate`, `-sql` |
| **Export & Replay**| `exit -s` / `export` | `exit -s`, `exit -s py`, `export pipeline.pt` | Export reproducible script (on exit or in-session) |
| | Batch Replay | `pytae pipeline.pt`, `pytae -i pipeline.pt` | Headless execution or interactive session preload |

### Detailed REPL Documentation Directory

For complete guides, configuration flags, edge cases, and cookbooks, see the dedicated topic documentation under **[`docs/repl/`](repl/)**:

- [**Master REPL Architecture & Command Hub**](repl/README.md) — Architectural pillars, 30-second quickstart, and master command reference table.
- [**Workbench, Ingestion & Multi-Table Management**](repl/workbench_tables.md) — Reader options (`-encoding`, `-dlim`, `-nrows`, `-opts`), glob loading, sample datasets, zero-copy `rename`, and table deallocation.
- [**In-Memory Pipelines & Data Inspection**](repl/pipelines_inspection.md) — 1:1 CLI verbs in RAM, assignment vs bare exploration semantics, multi-table joins, and non-destructive inspection.
- [**SQL & Python Interop (Ephemeral Python Sandboxing)**](repl/sql_python_interop.md) — ANSI SQL across tables, single-line & multi-line `py { ... }` blocks, pre-loaded `pd`/`pl`/`pt`, session-wide persistent imports, ephemeral RAM zeroing, and explicit `.to_pytae()` conversion.
- [**Session Variables (`@var`), Settings & Preferences**](repl/variables_config.md) — Session `@parameters`, nested configuration traversal, display preferences (`set`), and permanent configuration (`set save`).
- [**Checkpoints, History Audit, Pipeline Export & Replay**](repl/checkpoints_history_replay.md) — Ephemeral IPC snapshots, instant `restore`, milestone `-diff`, flight recorder `history`, script export (`exit -s`, `export`), and post-hoc conversion (`pytae -export`).

