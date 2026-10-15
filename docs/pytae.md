# Pytae — Architecture, File Ingestion & Missing Data Philosophy

This document outlines Pytae's foundational architecture, explaining how files are ingested and queried across both the **Python Library API** and the **Command-Line Interface (CLI)**, and detailing the "Zero Data Loss by Default" philosophy governing missing data handling (`dropna` / `drop_nulls`).

---

## Table of Contents

- [Core Philosophy: "Zero Data Loss by Default"](#core-philosophy-zero-data-loss-by-default)
- [How Files Are Read in Pytae](#how-files-are-read-in-pytae)
  - [Eager Ingestion (`pt.read`) vs. Lazy Evaluation (`pt.scan`)](#eager-ingestion-ptread-vs-lazy-evaluation-ptscan)
  - [Hardware Query Optimizations: Pushdowns at Work](#hardware-query-optimizations-pushdowns-at-work)
  - [Universal Container Constructor (`pt.DataFrame`)](#universal-container-constructor-ptdataframe)
  - [Dual-Mode Execution: Best of Both Lazy & Eager Without Manual `.collect()`](#dual-mode-execution-best-of-both-lazy--eager-without-manual-collect)
  - [CLI File Ingestion & Internal Lazy Graph Execution](#cli-file-ingestion--internal-lazy-graph-execution)
  - [Zero-Cost Metadata Inspection (No Full Table Read)](#zero-cost-metadata-inspection-no-full-table-read)
  - [Streaming Input: Piped Stdin, Clipboard, and Multi-File Pipelines](#streaming-input-piped-stdin-clipboard-and-multi-file-pipelines)
  - [Supported File Formats Matrix](#supported-file-formats-matrix)
  - [Side-by-Side Reading & Inspection Cheat Sheet](#side-by-side-reading--inspection-cheat-sheet)
- [How Pytae Compares to Pandas, Polars, and R/dplyr](#how-pytae-compares-to-pandas-polars-and-rdplyr)
  - [The Pandas Trap: Over-Aggressive Row Dropping](#the-pandas-trap-over-aggressive-row-dropping)
  - [The Polars Pitfall: Arrow Null vs. IEEE-754 Float NaN](#the-polars-pitfall-arrow-null-vs-ieee-754-float-nan)
  - [The R / dplyr Paradigm: Explicit Opt-In](#the-r--dplyr-paradigm-explicit-opt-in)
- [The "Option B" Specification](#the-option-b-specification)
  - [1. Bare Call: `how="all"` (Preserve Partial Rows)](#1-bare-call-howall-preserve-partial-rows)
  - [2. Targeted Call: `how="any"` (Enforce Required Keys)](#2-targeted-call-howany-enforce-required-keys)
  - [3. Explicit Overrides](#3-explicit-overrides)
  - [4. Dual Missing Value Cleaning (`drop_nans=True`)](#4-dual-missing-value-cleaning-drop_nanstrue)
- [Missing Values Inside Analytical Verbs](#missing-values-inside-analytical-verbs)
  - [Group Aggregations (`agg` / `-agg`)](#group-aggregations-agg---agg)
  - [2D Pivot Tables (`pivot` / `-pivot`)](#2d-pivot-tables-pivot---pivot)
  - [Frequency Tables (`freq` / `-freq`)](#frequency-tables-freq---freq)
  - [Feature Engineering (`mutate` / `-mutate`)](#feature-engineering-mutate---mutate)
  - [Arithmetic Invariance: Does `dropna` Change the `mean()`?](#arithmetic-invariance-does-dropna-change-the-mean)
- [Universal Aliasing & Full API Parity](#universal-aliasing--full-api-parity)
- [Comprehensive Examples: Python Library vs CLI](#comprehensive-examples-python-library-vs-cli)
  - [Example 1: Dropping Completely Blank Rows (Default)](#example-1-dropping-completely-blank-rows-default)
  - [Example 2: Dropping Rows Missing Critical Required Columns](#example-2-dropping-rows-missing-critical-required-columns)
  - [Example 3: Explicit Global Cleanup (`how="any"`)](#example-3-explicit-global-cleanup-howany)
  - [Example 4: Handling Float NaNs and Polars Nulls](#example-4-handling-float-nans-and-polars-nulls)
  - [Example 5: Pipeline Chaining with Aggregations](#example-5-pipeline-chaining-with-aggregations)
- [API Reference Summary](#api-reference-summary)

---

## Core Philosophy: "Zero Data Loss by Default"

In standard data science workflows, accidental data loss is one of the most common causes of skewed metrics, corrupted reporting, and incorrect modeling. A single missing optional field—such as a customer's secondary phone number or an optional shipping note—should **never** silently obliterate an entire multi-thousand-dollar transaction from a dataset.

Pytae adheres strictly to the principle of **Zero Data Loss by Default**:

1. **Conservative Row Elimination**: General cleanup operations only purge completely useless rows (i.e., rows where every single column is null/NaN).
2. **Intentional Filtering**: Rows are only filtered on specific columns when the user explicitly requests those columns or explicitly asks for `how="any"`.
3. **Preservation of NA Groups**: Analytical operations (`agg`, `pivot`, `freq`, `mutate`) retain missing/NA group categories rather than silently omitting them, ensuring you always know how much of your data lacks categorization.

---

## How Files Are Read in Pytae

File ingestion in Pytae is built on a high-throughput, multithreaded SIMD Polars core with seamless Apache Arrow memory layouts. 

Traditional tools (such as standard Pandas `pd.read_csv` or `pd.read_parquet`) read datasets **eagerly**, loading every single row and column into memory before downstream filtering or column selection can begin. On larger-than-RAM or multi-gigabyte datasets, this produces excessive I/O wait times and frequent Out-Of-Memory (OOM) crashes.

Pytae solves this problem across both Python and the Command-Line Interface through two complementary ingestion modes:
1. **Eager Ingestion (`pt.read`)**: Fast, immediate in-memory loading when you need interactive row access right away.
2. **Lazy Evaluation (`pt.scan` & CLI Pipeline)**: Constructs a symbolic execution plan, deferring all physical disk I/O until the final result is requested.

```
                    ┌────────────────────────┐
                    │      Source File       │
                    │ (.parquet, .csv, etc.) │
                    └───────────┬────────────┘
                                │
             ┌──────────────────┴──────────────────┐
             ▼                                     ▼
     Eager Ingestion                        Lazy Evaluation
      pt.read(path)                         pt.scan(path) / CLI
             │                                     │
             ▼                                     ▼
   Materializes to RAM                     Builds Query Graph
   • Polars SIMD Reader                    • Projection Pushdown
   • Immediate row access                  • Predicate Pushdown
   • In-memory DataFrame                   • Slice Pushdown
                                                   │
                                                   ▼
                                         Single .collect()
                                         Only reads what's needed!
```

---

### Eager Ingestion (`pt.read`) vs. Lazy Evaluation (`pt.scan`)

#### 1. `pt.read(path, **kwargs) -> DataFrame` (Eager)
`pt.read()` reads data immediately off disk into a `pytae.DataFrame` backed by a native Polars `DataFrame`. It automatically identifies the underlying format from the file extension and dispatches to the optimal SIMD reader.

```python
import pytae as pt

# Eager read from Parquet
df = pt.read("transactions.parquet")

# Eager read from CSV with custom options
df_csv = pt.read("measurements.csv", separator=";", encoding="utf-8")

# Eager read from remote URL
df_remote = pt.read("https://raw.githubusercontent.com/mwaskom/seaborn-data/master/penguins.csv")
```
- **Returns**: Eager `pytae.DataFrame` (`df.is_lazy == False`).
- **Best For**: Quick ad-hoc scripts, exploratory analysis, datasets that easily fit into memory, or when you need immediate row indexing and display.

#### 2. `pt.scan(path, **kwargs) -> DataFrame` (Lazy)
`pt.scan()` registers the file into Polars' query planner without reading the data into RAM. It returns a `pytae.DataFrame` with `is_lazy == True` wrapping a `polars.LazyFrame`.

```python
import pytae as pt

# Scans metadata only — zero rows are loaded into RAM!
lazy_df = pt.scan("massive_sales.parquet")

# Build a fluent analytical pipeline
query = (
    lazy_df
    .pt.select("region", "store_id", "revenue", "order_date")
    .pt.filter("revenue > 500.0 and region == 'West'")
    .pt.by("region", "store_id")
    .pt.agg(total_rev="sum(revenue)", num_orders="n")
    .pt.arrange("total_rev", ascending=False)
    .pt.head(10)
)

# Materialize execution: executes the optimized query plan
top_stores = query.collect()
```
- **Returns**: Lazy `pytae.DataFrame` (`df.is_lazy == True`).
- **Best For**: Large datasets, production ETL pipelines, queries needing filtering/column selection before loading, or systems with limited RAM.

---

### Hardware Query Optimizations: Pushdowns at Work

When using `pt.scan()` in Python or running the `pytae` CLI, the Polars query optimizer reorganizes operations to minimize hardware disk I/O, CPU decompression cycles, and RAM consumption.

```
Parquet on Disk (100 Columns, 50,000,000 Rows across 100 Row Groups)
┌──────────────────────────────────────────────────────────────────────────────┐
│ [Row Group 1] min(amount)=10, max(amount)=250  ──► SKIPPED (Predicate Pushdown)
│ [Row Group 2] min(amount)=150, max(amount)=8000 ──► READ ONLY col 'amount' & 'id'
│ [Row Group 3] min(amount)=5, max(amount)=90   ──► SKIPPED (Predicate Pushdown)
│ ...                                                                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### 1. Projection Pushdown (Column Pruning)
If a table has 80 columns but your pipeline only references `user_id` and `amount`:
- **Standard Pandas**: Reads all 80 columns from disk, allocates memory for all 80, and drops 78 columns in memory.
- **Pytae / Polars**: Passes the column projection to the Parquet/Arrow reader. **Only the 2 requested columns are read from disk.** The remaining 78 columns are never read, decompressed, or allocated in RAM.

#### 2. Predicate Pushdown (Row-Group Skipping)
If your pipeline filters `-filter "amount > 1000"`:
- Parquet files contain metadata headers with `min` and `max` statistics for each column within each row group (typically ~100,000 rows per group).
- Pytae evaluates the filter predicate against the row group statistics **before reading**.
- Any row group where `max(amount) <= 1000` is **completely skipped**. The disk read heads never touch those blocks, and zero decompression CPU cycles are consumed.

#### 3. Slice Pushdown (Early Termination)
If your pipeline ends with `.head(5)` or `-head 5`:
- The file reader terminates reading as soon as 5 matching rows are found, rather than scanning the entire file and discarding rows later.

---

### Universal Container Constructor (`pt.DataFrame`)

Pytae provides a universal constructor, `pt.DataFrame(data)`, that creates a Pytae DataFrame from almost any tabular data structure without unnecessary copies:

```python
import pytae as pt
import polars as pl
import pandas as pd
import pyarrow as pa

# 1. From an existing Polars DataFrame or LazyFrame (Zero-copy wrapper)
pldf = pl.DataFrame({"a": [1, 2, 3], "b": [10.0, 20.0, 30.0]})
df1 = pt.DataFrame(pldf)

# 2. From a Pandas DataFrame (Seamless Arrow conversion, original index preserved)
pdf = pd.DataFrame({"name": ["Alice", "Bob"], "age": [25, 30]})
df2 = pt.DataFrame(pdf)

# 3. From a PyArrow Table
arrow_tbl = pa.table({"x": [1, 2], "y": ["a", "b"]})
df3 = pt.DataFrame(arrow_tbl)

# 4. From raw Python dicts or records
df4 = pt.DataFrame({"id": [101, 102], "status": ["active", "pending"]})

# 5. Bundled Sample Datasets
penguins = pt.sample("penguins")
tips = pt.sample("tips")
flights = pt.sample("flights")
```

---

### Dual-Mode Execution: Best of Both Lazy & Eager Without Manual `.collect()`

One of the major pain points in modern data frameworks (such as native Polars) is the strict binary separation between eager `pl.DataFrame` and lazy `pl.LazyFrame`. In native Polars, they are distinct classes with diverging APIs; users must constantly remember when to call `.lazy()` to obtain query optimizations, and when to call `.collect()` to inspect results or pass data to downstream libraries.

Pytae eliminates this cognitive overhead through its **Dual-Mode Container Architecture**:

```
                       ┌────────────────────────────┐
                       │      pytae.DataFrame       │
                       │   (Universal Dual-Mode)    │
                       └─────────────┬──────────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
        Eager Under the Hood                    Lazy Under the Hood
         (pl.DataFrame)                          (pl.LazyFrame)
                 │                                       │
  All Verbs (.select, .filter,            All Verbs (.select, .filter,
  .mutate, .arrange, .dropna,             .mutate, .arrange, .dropna,
  .by, .agg) run in-memory                .by, .agg) chain lazy graph
                 │                                       │
                 ▼                                       ▼
       Immediate Results                   "Just-In-Time" Materialization
                                           • df.to_pandas()  • df.plot()
                                           • df.to_clip()    • df.values
                                           • df.to_parquet() (sink streaming!)
```

#### 1. Unified Fluent Grammar Across Both Modes
In Pytae, you write the exact same code whether your dataset is in-memory or lazy:
```python
import pytae as pt

# Mode A: Eager (in-memory)
df_eager = pt.read("sales.parquet")

# Mode B: Lazy (symbolic query graph)
df_lazy = pt.scan("sales.parquet")

# The exact same analytical pipeline runs on BOTH!
result = (
    df_lazy  # or df_eager
    .pt.filter("revenue > 1000")
    .pt.select("region", "revenue", "order_date")
    .pt.by("region")
    .pt.agg(total="sum(revenue)", count="n")
    .pt.arrange("total", ascending=False)
)
```
When chained on a lazy dataset, every verb invisibly returns another `pytae.DataFrame` with `is_lazy == True`. Polars continuously accumulates the logical query plan, preserving projection, predicate, and slice pushdowns without requiring intermediate `.collect()` calls.

#### 2. Zero-Cost Schema & Metadata Inspection
On a lazy dataset, standard property accesses do not trigger slow full-table scans:
- **`df.columns`**: Calls `self._df.collect_schema().names()`. Resolves column names directly from schema metadata with **0 rows read**.
- **`df.dtypes` / `df.schema`**: Calls `self._df.collect_schema()`. Returns Arrow type definitions without parsing table data.
- **`df.shape` & `len(df)`**: Evaluates `self._df.select(pl.len()).collect().item()`. Polars computes the exact row count in $\sim 0.01\text{ s}$ (often directly from Parquet metadata footers) without allocating column memory in RAM.

#### 3. "Just-In-Time" Automatic Collection
You only need materialized in-memory data when interfacing with Python objects, visualization packages, or the system clipboard. Pytae handles materialization **just-in-time** behind the scenes:

| Action / Method | What Happens Under the Hood |
|:---|:---|
| `df.to_pandas()` | Automatically collects the lazy plan and returns a Pandas DataFrame with original indices preserved. |
| `df.plot(...)` | Automatically collects the final analytical result and passes it to the Matplotlib Plotter. |
| `df.to_clip()` | Automatically collects the TSV stream and writes to the OS clipboard (`pbcopy`, `clip`, `xclip`). |
| `df.values` / `df.to_numpy()` | Materializes the minimum required columns to a NumPy ndarray. |
| `df.head(5)` | Slices the lazy plan with `.head(5)` and pushes the early termination limit down to the reader. |
| `repr(df)` | Formats the plan or preview without loading the full dataset into RAM. |

#### 4. Streaming Sinks: Out-of-Core Processing Without RAM Overhead
When exporting transformed datasets, you usually don't need the table held in Python RAM at all. 

When you call:
```python
query.to_parquet("summary.parquet")
# or
query.to_csv("summary.csv")
```
Pytae attempts **`self._df.sink_parquet()`** / **`sink_csv()`**. Polars streams data batches directly from the source disk through the filter/aggregation pipeline straight into the output file. You can transform a **100 GB dataset on an 8 GB laptop** without ever materializing the whole table in memory!

---

### CLI File Ingestion & Internal Lazy Graph Execution

When executing commands via the CLI (`pytae <path> [flags...]`), Pytae streams through an internal lazy pipeline:

```bash
pytae sales.parquet -filter "revenue > 1000" -select "region, revenue" -head 5
```

#### Under the Hood:
1. **Reader Resolution**: The CLI passes `sales.parquet` to `readers.get_reader(path)`, detecting the file format, compression, and separators.
2. **Lazy Initialization**: By default, Pytae invokes `to_polars_lazy()` on the reader. No row data is parsed into Python or RAM yet.
3. **Graph Construction**:
   - `-filter "revenue > 1000"` adds a filter node to the Polars query graph.
   - `-select "region, revenue"` adds a projection node.
   - `-head 5` adds a slice limit node.
4. **Hardware Pushdown & Single `.collect()`**: Polars pushes the projection and predicate directly into the Parquet reader. Only rows with `revenue > 1000` in row groups where `max(revenue) > 1000` are scanned, reading only the `region` and `revenue` columns off disk, and terminating immediately once 5 rows are collected.
5. **Formatted Output**: The resulting small, eager Polars DataFrame is formatted for terminal display (or emitted as TSV/JSONL if piped).

---

### Zero-Cost Metadata Inspection (No Full Table Read)

One of Pytae's most powerful capabilities is **Zero-Cost Metadata Inspection**. For structured columnar formats that carry schema and dimension information in their headers or footers (such as Parquet and SAS7BDAT), Pytae answers schema queries in milliseconds without scanning the table rows:

```bash
# Instant shape: Reads only Parquet footer metadata!
pytae huge_file.parquet -shape
# Output: (50000000, 48)  [0.01 seconds]

# Instant column list
pytae huge_file.parquet -cols

# Instant data types
pytae huge_file.parquet -dtype
```

| Operation | Command | Execution Cost |
|:---|:---|:---|
| Table Dimensions | `pytae file.parquet -shape` | **0.01s** (reads Parquet metadata footer, 0 rows scanned) |
| Column List | `pytae file.parquet -cols` | **0.01s** (reads schema names only) |
| Column Data Types | `pytae file.parquet -dtype` | **0.01s** (reads Arrow type definitions) |
| First $N$ Rows | `pytae file.parquet -head 5` | Reads only the first row group / batch |

---

### Streaming Input: Piped Stdin, Clipboard, and Multi-File Pipelines

Pytae is designed to integrate seamlessly into Unix command-line pipelines and multi-table environments:

#### 1. Piped Standard Input (`stdin` / `-`)
Pytae automatically detects piped data from standard input, or you can specify `-`:
```bash
# Automatically detects piped CSV input from curl or upstream command
curl -s "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/penguins.csv" | \
  pytae -select "species, island, body_mass_g" -dropna body_mass_g -head 5

# Explicit stdin indicator (-)
cat server_logs.csv | pytae - -filter "status == 500" -freq endpoint
```

#### 2. System Clipboard (`clip`)
Inspect data copied to your operating system clipboard directly in the terminal or Python:
```bash
# In the CLI: Ingests TSV/CSV from system clipboard
pytae clip -shape
pytae clip -by department -agg "avg_salary=mean(salary)"
```
```python
# In Python:
import pytae as pt
# Export any DataFrame directly to system clipboard
df.to_clip()
```

#### 3. Multi-File Pipelines (`-file`)
You can ingest multiple files simultaneously using alias syntax:
```bash
pytae -file "tx=transactions.parquet; cust=customers.csv" \
  -merge "left=tx, right=cust, on=customer_id, how=left" \
  -by cust.segment \
  -agg "total_sales=sum(tx.amount), count=n"
```

---

### Supported File Formats Matrix

| Format | File Extensions | Reader Engine | Lazy Scanning (`pt.scan`) | Zero-Cost Metadata | Compression Support |
|:---|:---|:---|:---:|:---:|:---:|
| **Apache Parquet** | `.parquet`, `.pq` | Native Polars SIMD / Arrow | Yes | Yes (Footer) | Snappy, ZSTD, Gzip (embedded) |
| **Delimited CSV** | `.csv` | Native Polars Fast CSV | Yes | Partial (Sampled) | `.csv.gz` |
| **Tab-Delimited** | `.tsv`, `.txt` | Native Polars Fast CSV (`\t`) | Yes | Partial (Sampled) | `.tsv.gz`, `.txt.gz` |
| **Pipe-Delimited** | `.dat` | Native Polars Fast CSV (`\|`, latin-1) | Yes | Partial (Sampled) | `.dat.gz` |
| **Line JSON** | `.jsonl`, `.ndjson` | Native Polars NDJSON | Yes | Partial (Sampled) | `.jsonl.gz`, `.ndjson.gz` |
| **Arrow / Feather** | `.ipc`, `.arrow`, `.feather` | Apache Arrow IPC Stream | Yes | Yes (Header) | LZ4, ZSTD (embedded) |
| **SAS Dataset** | `.sas7bdat` | PyReadstat $\to$ Polars | In-memory | Yes (Header) | Native SAS compression |
| **Excel** | `.xlsx`, `.xls` | Polars Excel / Calamine | In-memory | No | OpenXML zip |

---

### Side-by-Side Reading & Inspection Cheat Sheet

| Task | Python Library API | Command-Line Interface (CLI) |
|:---|:---|:---|
| **Eager Read** | `df = pt.read("data.parquet")` | `pytae data.parquet` |
| **Lazy Scan** | `df = pt.scan("data.parquet")` | `pytae data.parquet [flags...]` (auto-lazy) |
| **Inspect Shape** | `df.shape` | `pytae data.parquet -shape` |
| **Inspect Columns** | `df.columns` or `pt.cols(df)` | `pytae data.parquet -cols` |
| **Inspect Types** | `df.dtypes` | `pytae data.parquet -dtype` |
| **View First Rows** | `df.head(5)` | `pytae data.parquet -head 5` |
| **Sample Random Rows**| `df.sample(5)` or `pt.sample(df, 5)` | `pytae data.parquet -sample 5` |
| **Load Sample Dataset**| `pt.sample("penguins")` | `pytae sample:penguins` |
| **View Schema Summary**| `pt.glimpse(df)` | `pytae data.parquet -glimpse` |
| **Filter & Project** | `pt.scan("f.parquet").pt.select("a").pt.filter("a > 10").collect()` | `pytae f.parquet -select a -filter "a > 10"` |
| **Read Stdin** | `pt.read(sys.stdin)` | `cat f.csv \| pytae -select a` |
| **Read Clipboard** | `pd.read_clipboard().pt` | `pytae clip -shape` |
| **Custom Delimiter** | `pt.read("f.txt", separator=";")` | `pytae f.txt -dlim ";"` |

---

## How Pytae Compares to Pandas, Polars, and R/dplyr

| Feature / Behavior | Pandas | Polars | R / dplyr | Pytae (Option B) |
|:---|:---|:---|:---|:---|
| **Bare Call (`df.dropna()`)** | Drops rows if *any* column is NA (`how='any'`) | Drops rows if *any* column is `null` | No global verb; requires `filter(!is.na(col))` or `tidyr::drop_na()` | **Drops only 100% blank rows (`how='all'`)** |
| **Float `NaN` vs Arrow `null`** | Conflates both into `np.nan` / `pd.NA` | Differentiates; `drop_nulls()` **ignores** `NaN`! | Treats `NA` and `NaN` distinctly | **Drops both `null` and `NaN` by default (`drop_nans=True`)** |
| **Analytical Verbs (`groupby`, `pivot`)** | `dropna=True` by default (drops NA groups!) | Preserves `null` group keys | `group_by()` preserves `NA` groups | **`dropna=False` by default (Zero Data Loss)** |
| **Targeted Columns (`df.dropna("a", "b")`)** | `subset=['a', 'b']`, drops if any is NA | `subset=['a', 'b']`, drops if any is null | `tidyr::drop_na(a, b)` | **Drops if any specified column is NA (`how='any'`)** |
| **CLI & Library Aliasing** | `dropna()` only | `drop_nulls()` only | `drop_na()` | **`dropna`, `drop_nulls`, `drop_na` (100% interchangeable)** |

### The Pandas Trap: Over-Aggressive Row Dropping
In Pandas, running `df.dropna()` without arguments defaults to `how="any"`. On wide real-world tables (e.g. 50+ columns), almost every row contains at least one optional missing value. A bare `df.dropna()` frequently drops **90% to 100% of valid business data** without warning.

Furthermore, in Pandas `df.groupby(...).mean()`, the default setting has historically been `dropna=True`, silently dropping all rows belonging to an unassigned or missing category.

### The Polars Pitfall: Arrow Null vs. IEEE-754 Float NaN
Polars adopts the Apache Arrow specification, which separates missingness into two distinct concepts:
- **`null`**: A bitmask indicating absence of data (applies to integers, strings, floats, dates, structs).
- **`NaN`**: A valid 64-bit IEEE-754 floating-point numerical value representing an invalid computation (e.g., `0.0 / 0.0`).

Calling `pl.DataFrame.drop_nulls()` **only drops Arrow `null`s**. It leaves float `NaN` values completely untouched in memory! When performing downstream arithmetic:
```python
# Polars native behavior:
pl.Series([10.0, float("nan")]).mean()  # Returns NaN! Float NaN poisons arithmetic!
```
Because `drop_nulls()` leaves `NaN` in place, users frequently encounter arithmetic poisoning.

### The R / dplyr Paradigm: Explicit Opt-In
In R's `tidyverse` (`dplyr`), data loss is prevented by design:
- `dplyr::group_by()` always preserves `NA` groups as a distinct category.
- Summaries do not drop missing data silently; functions require explicit opt-in (e.g., `mean(x, na.rm = TRUE)`).
- `tidyr::drop_na()` is used when row dropping is explicitly desired.

Pytae adopts the best of the R philosophy combined with high-performance vector execution in Polars.

---

## The "Option B" Specification

Pytae implements **Option B** across the entire library and CLI.

### 1. Bare Call: `how="all"` (Preserve Partial Rows)
When called without column arguments, `dropna` operates as a safe table-cleaning sweep:
```python
# Python
clean_df = df.dropna()
# or
clean_df = df.drop_nulls()
```
```bash
# CLI
pytae data.parquet -dropna
# or
pytae data.parquet -drop_nulls
```
- **Behavior**: Drops **only** rows where every single column is null/NaN.
- **Outcome**: Valid rows with partial missing values remain intact. No business data is lost.

### 2. Targeted Call: `how="any"` (Enforce Required Keys)
When one or more columns are explicitly specified, `dropna` treats them as mandatory:
```python
# Python
clean_df = df.dropna("customer_id", "order_date")
# or
clean_df = df.drop_nulls("customer_id", "order_date")
```
```bash
# CLI
pytae data.parquet -dropna "customer_id, order_date"
# or
pytae data.parquet -drop_nulls "customer_id, order_date"
```
- **Behavior**: Drops any row where *at least one* of the specified columns is missing.
- **Outcome**: Guarantees that the resulting dataset contains complete, non-null values for the required fields.

### 3. Explicit Overrides
You can explicitly override the default `how` parameter at any time:
```python
# Python: Force drop any row with ANY null across the entire dataframe
df.dropna(how="any")

# Python: Drop only if BOTH specified columns are null
df.dropna("phone", "email", how="all")
```
```bash
# CLI: Explicit how=any across entire dataframe
pytae data.parquet -dropna how=any

# CLI: Drop only if both specified columns are missing
pytae data.parquet -dropna "phone, email, how=all"
```

### 4. Dual Missing Value Cleaning (`drop_nans=True`)
Pytae bridges Arrow `null` and IEEE-754 `NaN`. By default (`drop_nans=True`), Pytae inspects the column data types in the schema:
- For floating-point columns (`Float32`, `Float64`), it builds an expression combining `.is_null() | .is_nan()`.
- For all other columns (strings, ints, dates, booleans), it checks `.is_null()`.
- If you specifically need to preserve IEEE-754 float `NaN` values while only purging Arrow nulls, pass `drop_nans=False` (or `nans=false` in the CLI).

---

## Missing Values Inside Analytical Verbs

Pytae maintains consistent "Zero Data Loss by Default" across all analytical operations.

### Group Aggregations (`agg` / `-agg`)
When grouping data using `.pt.by("region")` or CLI `-by region -agg ...`:
- **Default**: `dropna=False` / `drop_nulls=False`.
- **Effect**: Rows where `region` is `null` form their own grouping category (e.g. `null | count=12 | sum=1500`).
- **Override**: Pass `dropna=True` or `drop_nulls=True` inside `agg(...)` or `-agg "sum, dropna=true"` to omit null groups.

### 2D Pivot Tables (`pivot` / `-pivot`)
When pivoting data into cross-tabulations:
- **Default**: `dropna=False` / `drop_nulls=False`.
- **Effect**: If the row (`r`) or column (`c`) variables contain `null`s, they are included as their own row or column in the pivot table, preventing invisible row drops.
- **Override**: Pass `dropna=True` or `drop_nulls=True` inside `pivot(...)` or `-pivot "..., dropna=true"`.

### Frequency Tables (`freq` / `-freq`)
When generating categorical distributions:
- **Default**: `dropna=False`.
- **Effect**: Null/NaN entries are displayed as an explicit `NA` category with their frequency count and percentage.
- **Override**: Pass `dropna=True` or CLI `-freq col, dropna=true`.

### Feature Engineering (`mutate` / `-mutate`)
When creating calculated columns:
- **Default**: `dropna=False`.
- **Effect**: Window functions and grouped computations evaluate across the `null` group just like any other group.

### Arithmetic Invariance: Does `dropna` Change the `mean()`?

A common question is: *If I calculate the mean of a column, does calling `dropna` first change the mathematical answer?*

#### Case 1: Single-Column Metric (Invariant)
$$\bar{x} = \frac{\sum_{i=1}^N x_i}{N}$$
In both Polars and Pandas, `mean()` inherently divides the sum of non-null values by the count of non-null values ($N$). 
If a column contains `[10, 20, null]`, the mean is:
$$\frac{10 + 20}{2} = 15.0$$
Dropping the `null` beforehand leaves `[10, 20]`, whose mean is also $15.0$. **The numeric result is identical.**

#### Case 2: Multi-Column Cross-Contamination (Catastrophic Data Loss)
The danger arises when dropping rows across multiple columns (e.g., Pandas' default `df.dropna()`):
Suppose you have:
| sales | feedback_notes |
|:---|:---|
| 1000 | "Great service" |
| 5000 | `null` |
| 2000 | "Will return" |

If you run Pandas `df.dropna()` before computing `df["sales"].mean()`:
- Row 2 is dropped simply because `feedback_notes` is null!
- The mean of `sales` changes from $\frac{1000 + 5000 + 2000}{3} = 2666.67$ to $\frac{1000 + 2000}{2} = 1500.00$.
- **You have introduced massive statistical bias and data loss.**

Pytae's Option B prevents this disaster entirely:
- Calling `df.dropna()` bare preserves Row 2 because it is not 100% blank.
- `df["sales"].mean()` accurately computes $2666.67$.

---

## Universal Aliasing & Full API Parity

Pytae provides complete 100% interchangeability across terminology:

| Operation | Canonical | Aliases |
|:---|:---|:---|
| **Python Function** | `pt.dropna(df, ...)` | `pt.drop_nulls(df, ...)`, `pt.drop_na(df, ...)` |
| **DataFrame Method** | `df.dropna(...)` | `df.drop_nulls(...)`, `df.drop_na(...)` |
| **Grouped DataFrame** | `df.pt.by(...).dropna(...)` | `df.pt.by(...).drop_nulls(...)`, `df.pt.by(...).drop_na(...)` |
| **Accessor Method** | `df.pt.dropna(...)` | `df.pt.drop_nulls(...)`, `df.pt.drop_na(...)` |
| **CLI Flags** | `pytae file -dropna` | `pytae file -drop_nulls`, `pytae file -drop_na` |
| **Keyword Arguments** | `dropna=True` | `drop_nulls=True` (in `agg`, `pivot`, etc.) |

---

## Comprehensive Examples: Python Library vs CLI

### Example 1: Dropping Completely Blank Rows (Default)

#### Python API
```python
import pytae as pt

# Lazy scan or eager DataFrame
df = pt.read("transactions.parquet")

# Drops ONLY rows where all columns are null or NaN
clean_df = df.dropna()
# Exactly identical to:
clean_df = df.drop_nulls()
```

#### CLI
```bash
# Bare flag defaults to how='all'
pytae transactions.parquet -dropna -shape

# Using the Polars alias
pytae transactions.parquet -drop_nulls -shape
```

---

### Example 2: Dropping Rows Missing Critical Required Columns

#### Python API
```python
import pytae as pt

df = pt.read("penguins.parquet")

# Drops rows where body_mass_g OR sex is missing (how='any' on specified subset)
complete_cases = df.dropna("body_mass_g", "sex")

# Accessor style
complete_cases = df.pt.dropna("body_mass_g", "sex")
```

#### CLI
```bash
# Drop rows where body_mass_g is missing (344 -> 342 rows)
pytae penguins.parquet -dropna body_mass_g -shape

# Multiple required columns
pytae penguins.parquet -drop_nulls "body_mass_g, sex" -shape
```

---

### Example 3: Explicit Global Cleanup (`how="any"`)

#### Python API
```python
import pytae as pt

df = pt.read("penguins.parquet")

# Drops any row that contains ANY null or NaN in ANY column (344 -> 333 rows)
strict_complete = df.dropna(how="any")
```

#### CLI
```bash
# Explicit how=any flag
pytae penguins.parquet -dropna how=any -shape

# Or with drop_nulls
pytae penguins.parquet -drop_nulls how=any -shape
```

---

### Example 4: Handling Float NaNs and Polars Nulls

#### Python API
```python
import polars as pl
import pytae as pt

# Dataset containing both Arrow null and IEEE-754 float NaN
raw_data = pl.DataFrame({
    "id": [1, 2, 3, 4],
    "value": [10.5, None, float("nan"), 40.0]
})

df = pt.DataFrame(raw_data)

# By default, drop_nans=True cleans BOTH None (null) and float('nan')
clean = df.dropna("value")
# Result contains: [10.5, 40.0] (2 rows)

# If you explicitly want to keep float('nan') and only drop Arrow nulls:
keep_nans = df.dropna("value", drop_nans=False)
# Result contains: [10.5, nan, 40.0] (3 rows)
```

#### CLI
```bash
# Cleans both null and NaN by default
pytae measurements.csv -dropna value

# Retain float NaNs while dropping nulls
pytae measurements.csv -dropna "value, drop_nans=false"
```

---

### Example 5: Pipeline Chaining with Aggregations

#### Python API
```python
import pytae as pt

penguins = pt.sample("penguins")

# Drop rows missing body mass, group by species, and aggregate
result = (
    penguins
    .pt.dropna("body_mass_g")
    .pt.by("species")
    .pt.agg(count="n", avg_mass="mean(body_mass_g)")
)
print(result)
```

#### CLI
```bash
pytae penguins.parquet \
  -dropna body_mass_g \
  -by species \
  -agg "count = n, avg_mass = mean(body_mass_g)"
```

**Output:**
```
species    count    avg_mass
Adelie       151     3700.66
Chinstrap     68     3733.09
Gentoo       123     5076.02
```

---

## API Reference Summary

### Function: `pt.dropna` / `pt.drop_nulls` / `pt.drop_na`
```python
pt.dropna(
    df: DataFrame | pl.DataFrame | pd.DataFrame,
    *cols: str,
    how: str | None = None,
    drop_nans: bool = True,
) -> DataFrame
```
- **`df`**: Input table (Pytae DataFrame, Polars DataFrame/LazyFrame, or Pandas DataFrame).
- **`*cols`**: Optional column names to inspect.
- **`how`**: `'all'` or `'any'`. If omitted, defaults to `'all'` when `cols` is empty, or `'any'` when `cols` is specified.
- **`drop_nans`**: `bool` (default `True`). When `True`, drops float IEEE-754 `NaN`s in addition to Arrow `null`s.

### Method: `DataFrame.dropna` / `DataFrame.drop_nulls` / `DataFrame.drop_na`
```python
df.dropna(*cols: str, how: str | None = None, drop_nans: bool = True) -> DataFrame
```

### CLI Flag: `-dropna` / `-drop_nulls` / `-drop_na`
```bash
pytae <path> -dropna [SPEC]
```
- Bare `-dropna` $\rightarrow$ `how="all"` (Zero Data Loss).
- `-dropna "col1, col2"` $\rightarrow$ `how="any"` on specified columns.
- `-dropna how=any` $\rightarrow$ Drops rows with any missing value across all columns.
- `-dropna "col1, how=all"` $\rightarrow$ Drops row only if all listed columns are missing.
- `-dropna "col1, drop_nans=false"` $\rightarrow$ Preserves float NaNs.

