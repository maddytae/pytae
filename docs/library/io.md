# Data Input & Output (I/O) — Ingestion, Streaming, and Sinks

`pytae` provides a unified, high-throughput I/O engine powered by a 100% native multithreaded SIMD Polars core with seamless Apache Arrow memory layouts.

This guide covers:
- **Eager Reading (`pt.read`)**: Fast, immediate in-memory loading.
- **Lazy Scanning (`pt.scan`)**: Query pushdown, projection pruning, and predicate skipping.
- **Dual-Mode Execution**: Writing fluent pipelines without manual `.collect()` juggling.
- **Universal Constructor (`pt.DataFrame`)**: Seamless interop across Polars, Pandas, Arrow, and Python dictionaries.
- **Writing Data (Sinks)**: Out-of-core streaming exports (`to_parquet`, `to_csv`, `to_pandas`, `to_clip`).
- **Bundled Datasets & Sampling**: `pt.sample()` and random row sampling.

---

## Table of Contents

- [Eager Ingestion (`pt.read`) vs. Lazy Evaluation (`pt.scan`)](#eager-vs-lazy)
- [Eager Reading (`pt.read`)](#eager-reading)
  - [Supported File Formats](#supported-formats)
  - [Custom Delimiters & Encodings](#custom-delimiters)
  - [Remote URLs & Compressed Files](#remote-and-compressed)
- [Lazy Scanning & Query Pushdowns (`pt.scan`)](#lazy-scanning)
  - [Projection Pushdown (Column Pruning)](#projection-pushdown)
  - [Predicate Pushdown (Row-Group Skipping)](#predicate-pushdown)
  - [Slice Pushdown (Early Termination)](#slice-pushdown)
  - [Performance Comparison: When to Use Read vs. Scan](#read-vs-scan-performance)
- [Dual-Mode Execution: Best of Both Without `.collect()`](#dual-mode-execution)
  - [Zero-Cost Schema & Metadata Inspection](#zero-cost-metadata)
  - [Just-In-Time Materialization](#just-in-time)
- [Universal Constructor (`pt.DataFrame`)](#universal-constructor)
- [Data Output & Export Sinks](#data-output)
  - [Streaming Parquet (`to_parquet`)](#to-parquet)
  - [Streaming CSV (`to_csv`)](#to-csv)
  - [Pandas & Polars Interop (`to_pandas`, `to_polars`)](#interop)
  - [System Clipboard (`to_clip`)](#to-clip)
- [Bundled Sample Datasets & Row Sampling](#sample-datasets-and-sampling)
  - [Loading Bundled Datasets (`pt.sample`)](#bundled-datasets)
  - [Random Row Sampling (`df.sample`)](#row-sampling)
- [Joining & Stacking Datasets (`join`, `concat`)](#joining-and-stacking)
  - [Joining Datasets (`df.join`, `pt.join`)](#joining-datasets)
  - [Join Strategies (`how`)](#join-strategies)
  - [Differing Key Names & Colon Notation](#differing-keys)
  - [Stacking Datasets (`pt.concat`, `df.concat`)](#concat-datasets)
  - [Transparent Polars Verb Delegation](#polars-delegation)
- [I/O API Quick Reference](#api-quick-reference)

---

<a id="eager-vs-lazy"></a>
## Eager Ingestion (`pt.read`) vs. Lazy Evaluation (`pt.scan`)

Traditional data science tools (such as standard Pandas `pd.read_csv` or `pd.read_parquet`) read datasets **eagerly**, loading every row and column into RAM before any filtering or column selection can begin. On larger-than-RAM or multi-gigabyte datasets, this produces excessive I/O wait times and Out-Of-Memory (OOM) crashes.

Pytae provides two complementary paradigms:

```
                    ┌────────────────────────┐
                    │      Source File       │
                    │ (.parquet, .csv, etc.) │
                    └───────────┬────────────┘
                                │
             ┌──────────────────┴──────────────────┐
             ▼                                     ▼
     Eager Ingestion                        Lazy Evaluation
      pt.read(path)                         pt.scan(path)
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

<a id="eager-reading"></a>
## Eager Reading (`pt.read`)

`pt.read()` reads data off disk immediately into a `pytae.DataFrame` backed by a native Polars `DataFrame`. It automatically infers the file format from the file extension.

```python
import pytae as pt

# Direct reading from Parquet
df = pt.read("transactions.parquet")

# Direct reading from CSV
df_csv = pt.read("customers.csv")
```

### Supported File Formats

| Format | Extension | Underlying Engine | Auto-Detected Defaults |
|:---|:---|:---|:---|
| **Parquet** | `.parquet`, `.pq` | Native Polars SIMD Parquet | Snappy, ZSTD, Gzip compression |
| **CSV** | `.csv` | Native Polars Fast CSV | Comma-separated (`,`), UTF-8 |
| **TSV / Tab Text** | `.tsv`, `.txt` | Native Polars Fast CSV | Tab-separated (`\t`) |
| **DAT / Pipe Text**| `.dat` | Native Polars Fast CSV | Pipe-separated (`\|`), Latin-1 |
| **Line JSON** | `.jsonl`, `.ndjson` | Native Polars NDJSON | Newline-delimited JSON records |
| **Excel** | `.xlsx`, `.xls` | Calamine / OpenXML | Primary worksheet |
| **Compressed** | `.csv.gz`, `.txt.gz`, `.dat.gz`, `.ndjson.gz` | Native Gzip Stream | Auto-decompression on read |

### Custom Delimiters & Encodings

Any additional keyword arguments passed to `pt.read()` are forwarded directly to the underlying Polars reader:

```python
# Custom delimiter and encoding
df = pt.read("data.csv", separator=";", encoding="latin-1")

# Read specific columns only
df = pt.read("data.parquet", columns=["user_id", "total_amount"])

# Limit rows read into memory
df = pt.read("huge_data.csv", n_rows=1000)
```

### Remote URLs & Compressed Files

`pt.read()` natively accepts HTTP and HTTPS URLs and compressed archives:

```python
# Read directly from public HTTPS URL
url = "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/penguins.csv"
penguins = pt.read(url)

# Read directly from gzipped CSV
logs = pt.read("access_logs.csv.gz")
```

---

<a id="lazy-scanning"></a>
## Lazy Scanning & Query Pushdowns (`pt.scan`)

`pt.scan()` registers the dataset into Polars' query planner without loading row data into RAM. It returns a `pytae.DataFrame` with `is_lazy == True` wrapping a `polars.LazyFrame`.

```python
import pytae as pt

# Instant scan: reads only header/schema metadata (0 rows in RAM!)
lazy_df = pt.scan("massive_sales.parquet")

# Build a fluent analytical pipeline
query = (
    lazy_df.pt.select("region", "store_id", "revenue", "order_date")
    .pt.filter("revenue > 500.0 and region == 'West'")
    .pt.by("region", "store_id")
    .pt.agg(total_rev="sum(revenue)", num_orders="n")
    .pt.arrange("total_rev", ascending=False)
    .pt.head(10)
)

# Materialize execution: executes the fully optimized query plan
top_stores = query.collect()
```

### Hardware Query Optimizations

When using `pt.scan()`, the Polars query optimizer reorganizes operations to minimize hardware disk I/O, CPU decompression cycles, and RAM consumption.

```
Parquet on Disk (100 Columns, 50,000,000 Rows across 100 Row Groups)
┌──────────────────────────────────────────────────────────────────────────────┐
│ [Row Group 1] min(amount)=10, max(amount)=250   ──► SKIPPED (Predicate Pushdown)
│ [Row Group 2] min(amount)=150, max(amount)=8000 ──► READ ONLY col 'amount' & 'id'
│ [Row Group 3] min(amount)=5, max(amount)=90    ──► SKIPPED (Predicate Pushdown)
│ ...                                                                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### 1. Projection Pushdown (Column Pruning)
If a table has 80 columns but your pipeline only references `user_id` and `amount`:
- **Standard Pandas**: Reads all 80 columns from disk, allocates memory for all 80, and drops 78 columns in memory.
- **Pytae / Polars**: Passes the column projection down to the reader. **Only the 2 requested columns are read off disk.** The remaining 78 columns are never read, decompressed, or allocated in RAM.

#### 2. Predicate Pushdown (Row-Group Skipping)
If your pipeline filters `.pt.filter("amount > 1000")`:
- Parquet files contain metadata headers with `min` and `max` statistics for each column within each row group (~100,000 rows per group).
- Pytae evaluates the filter predicate against the row group statistics **before reading**.
- Any row group where `max(amount) <= 1000` is **completely skipped**. The disk read heads never touch those blocks, and zero decompression CPU cycles are consumed.

#### 3. Slice Pushdown (Early Termination)
If your pipeline ends with `.head(5)`:
- The file reader terminates reading as soon as 5 matching rows are obtained, rather than reading the entire file and discarding the rest.

<a id="read-vs-scan-performance"></a>
### Performance Comparison: When to Use Read vs. Scan

| Scenario | Recommended API | Why? |
|:---|:---:|:---|
| **Selective Query on Large File** (filtering rows or selecting specific columns) | `pt.scan()` | **10x–50x faster**: Projection and predicate pushdowns avoid reading 90%+ of the file off disk. |
| **Quick Peek at Large File** (`.head(5)`) | `pt.scan()` | **Instant (~0.003s)**: Slice pushdown terminates reading after the first batch. |
| **Full Ingestion of Entire CSV** (all columns, all rows, no filtering) | `pt.read()` | **Faster than `scan().collect()`**: Eager parser reads contiguous bytes into Arrow memory without streaming query-engine chunk coordination. |
| **Small to Medium Datasets (< 500 MB)** | `pt.read()` | Simpler immediate row access without query planning overhead. |

---

<a id="dual-mode-execution"></a>
## Dual-Mode Execution: Best of Both Without `.collect()`

In native Polars, `pl.DataFrame` and `pl.LazyFrame` are two separate classes with distinct APIs. Users must constantly remember when to call `.lazy()` and when to call `.collect()`.

In `pytae`, **both eager and lazy tables are wrapped in the universal `pytae.DataFrame` container**:
- Every fluent verb (`.select()`, `.filter()`, `.mutate()`, `.arrange()`, `.dropna()`, `.by()`, `.agg()`) works identically on both eager and lazy data.
- If you start with `pt.scan()`, operations chain invisibly as a lazy query graph.

<a id="zero-cost-metadata"></a>
### Zero-Cost Schema & Metadata Inspection
On a lazy dataset, inspecting metadata does not trigger a slow, full table scan:
- **`df.columns`**: Calls `collect_schema().names()`. Resolves column names directly from schema metadata with **0 rows read**.
- **`df.dtypes` / `df.schema`**: Calls `collect_schema()`. Returns Arrow type definitions without parsing table data.
- **`df.shape` & `len(df)`**: Evaluates `_df.select(pl.len()).collect().item()`. Polars computes the exact row count in $\sim 0.01\text{ s}$ (often directly from Parquet metadata footers) without allocating column memory in RAM.

<a id="just-in-time"></a>
### Just-In-Time Materialization
Pytae materializes data **just-in-time** when external libraries or output sinks require concrete values:

| Action / Method | What Happens Behind the Scenes |
|:---|:---|
| `df.to_pandas()` | Collects the lazy plan and returns a Pandas DataFrame with original indices preserved. |
| `df.plot(...)` | Collects the analytical result and passes it to the Matplotlib Plotter. |
| `df.to_clip()` | Collects the TSV stream and copies to the OS clipboard (`pbcopy`, `clip`, `xclip`). |
| `df.values` / `to_numpy()` | Materializes the minimum required columns to a NumPy ndarray. |
| `df.head(5)` | Slices the lazy plan with `.head(5)` and pushes the early termination limit down to the reader. |

---

<a id="universal-constructor"></a>
## Universal Constructor (`pt.DataFrame`)

`pt.DataFrame(data)` creates a Pytae DataFrame from almost any tabular data structure:

```python
import pytae as pt
import polars as pl
import pandas as pd
import pyarrow as pa

# 1. From an existing Polars DataFrame or LazyFrame (Zero-copy wrapper)
pldf = pl.DataFrame({"a": [1, 2, 3], "b": [10.0, 20.0, 30.0]})
df1 = pt.DataFrame(pldf)

# 2. From a Pandas DataFrame (Seamless Arrow conversion, original index preserved)
pdf = pd.DataFrame({"name": ["Alice", "Bob"], "age": [25, 30]}, index=["row1", "row2"])
df2 = pt.DataFrame(pdf)

# 3. From a PyArrow Table
arrow_tbl = pa.table({"x": [1, 2], "y": ["a", "b"]})
df3 = pt.DataFrame(arrow_tbl)

# 4. From raw Python dicts or records
df4 = pt.DataFrame({"id": [101, 102], "status": ["active", "pending"]})
```

---

<a id="data-output"></a>
## Data Output & Export Sinks

Pytae provides high-performance output sinks for saving, converting, or copying transformed tables.

<a id="to-parquet"></a>
### Streaming Parquet Export (`to_parquet`)

When writing transformed data to Parquet:
```python
df.to_parquet("output.parquet")
```
- **On eager DataFrames**: Writes directly via multithreaded SIMD Arrow serialization.
- **On lazy DataFrames**: Automatically attempts Polars' out-of-core streaming engine (**`sink_parquet()`**). Data streams directly from the source disk through your pipeline into the destination file. You can transform a **100 GB dataset on an 8 GB laptop** without running out of RAM!

<a id="to-csv"></a>
### Streaming CSV Export (`to_csv`)

```python
df.to_csv("output.csv")
```
- Automatically attempts streaming **`sink_csv()`** on lazy plans.
- Respects custom separators: `df.to_csv("output.tsv", separator="\t")`.

<a id="interop"></a>
### Pandas & Polars Interoperability

```python
# Convert to Pandas DataFrame (original indices and column types preserved)
pdf = df.to_pandas()

# Extract the underlying Polars DataFrame (collecting if lazy)
pldf = df.to_polars()
```

<a id="to-clip"></a>
### System Clipboard Export (`to_clip`)

Quickly paste analytical results into Slack, Excel, or Google Sheets:
```python
# Copies the table to clipboard as clean TSV (without row index numbers)
df.to_clip()
```
Works across macOS (`pbcopy`), Windows (`clip`), and Linux (`xclip`).

---

<a id="sample-datasets-and-sampling"></a>
## Bundled Sample Datasets & Row Sampling

<a id="bundled-datasets"></a>
### Loading Bundled Datasets (`pt.sample`)

Pytae bundles **21 real-world datasets** stored internally in Parquet for instant experimentation and testing:

```python
import pytae as pt

# Load Palmer penguins (default dataset)
penguins = pt.sample("penguins")  # or simply pt.sample()

# Other popular datasets:
tips = pt.sample("tips")
flights = pt.sample("flights")
titanic = pt.sample("titanic")
diamonds = pt.sample("diamonds")

# View all available dataset names:
print(pt.sample_data.keys())
# ('anagrams', 'anscombe', 'attention', 'brain_networks', 'car_crashes',
#  'diamonds', 'dots', 'dowjones', 'exercise', 'flights', 'fmri', 'geyser',
#  'glue', 'healthexp', 'iris', 'mpg', 'penguins', 'planets', 'seaice', 'taxis', 'titanic')
```

<a id="row-sampling"></a>
### Random Row Sampling (`df.sample`)

Just like `df.head()` and `df.tail()`, you can randomly sample rows from any DataFrame:

```python
import pytae as pt

df = pt.read("transactions.parquet")

# 1. Sample N rows (default is 5)
sampled = df.sample(10)

# 2. Sample a percentage / fraction of rows
sampled = df.sample(frac=0.15, seed=42)

# 3. Reproducible sampling with a seed
sampled = df.sample(5, seed=42)

# 4. Sampling with replacement
sampled = df.sample(10, replace=True)

# 5. Group-aware sampling (samples N rows from each group!)
sampled = df.pt.by("category").sample(2, seed=42)

# 6. Top-level function syntax
sampled = pt.sample(df, 5, seed=42)
```

---

<a id="joining-and-stacking"></a>
## Joining & Stacking Datasets (`join`, `concat`)

Pytae provides first-class support for relational joins and tabular stacking powered directly by Polars' multithreaded SIMD vector engine. Rather than introducing intermediate abstractions, Pytae adopts Polars' native **`join`** and **`concat`** verbs so you can combine datasets without ever breaking your method chain.

---

<a id="joining-datasets"></a>
### Joining Datasets (`df.join`, `pt.join`)

Join two tables on shared or distinct keys with `df1.join(df2)` or `pt.join(df1, df2)`:

```python
import pytae as pt

orders = pt.read("orders.parquet")
customers = pt.read("customers.csv")

# Fluent method chain: join -> filter -> mutate -> arrange
result = (
    orders.join(customers, on="customer_id", how="left")
    .filter("order_amount > 50")
    .by("region")
    .mutate(running_total="cumsum(order_amount)")
    .arrange("-running_total")
)
```

#### Automatic Key Detection
If `on`, `left_on`, and `right_on` are omitted, Pytae automatically discovers the intersecting column names between both tables:

```python
# Automatically joins on common columns (e.g., ["user_id"])
joined = df1.join(df2)
```

---

<a id="join-strategies"></a>
### Join Strategies (`how`)

Pytae supports all 7 native Polars join strategies:

| Strategy (`how`) | Description |
|:---|:---|
| **`"inner"`** (default) | Returns rows where keys match in both tables. |
| **`"left"`** | Returns all left rows plus matching right rows (unmatched right filled with null). |
| **`"right"`** | Returns all right rows plus matching left rows. |
| **`"full"`** | Full outer join; preserves all rows from both tables. |
| **`"semi"`** | **Filtering join**: Returns rows from the left table that have a match in the right table (without duplicating columns). |
| **`"anti"`** | **Filtering join**: Returns rows from the left table that have NO match in the right table. |
| **`"cross"`** | Cartesian product of every left row with every right row (does not take join keys). |

```python
# Fast membership filtering with semi join:
active_orders = orders.join(active_users, on="user_id", how="semi")

# Finding churned users with anti join:
churned_users = users.join(recent_logins, on="user_id", how="anti")
```

---

<a id="differing-keys"></a>
### Differing Key Names & Colon Notation

When key columns have different names between tables, pass `left_on` and `right_on`, or use CLI-compatible colon notation `on="left_key:right_key"`:

```python
# Explicit left_on / right_on
res = orders.join(users, left_on="cust_id", right_on="user_id", how="left")

# Concise colon notation
res = orders.join(users, on="cust_id:user_id", how="left")
```

#### Lazy Join Query Optimization
When joining two lazy datasets created via `pt.scan()`, Pytae preserves the lazy execution graph. Polars optimizes join predicate pushdowns across both files before reading rows from disk:

```python
# Zero upfront memory: Polars plans the join and pushes filters down to disk
lazy_joined = (
    pt.scan("orders_100M.parquet").join(pt.scan("customers.csv"), on="customer_id").filter("region == 'EMEA'").collect()
)
```

---

<a id="concat-datasets"></a>
### Stacking Datasets (`pt.concat`, `df.concat`)

Concatenate datasets vertically (row-wise) or horizontally (column-wise) using `pt.concat([dfs...])` or `df1.concat(df2, df3)`:

```python
# 1. Vertical stacking (identical schemas)
q_all = pt.concat([q1, q2, q3, q4])

# 2. Method-chain stacking
combined = q1.concat(q2, q3)

# 3. Automatic schema alignment (diagonal_relaxed fallback)
# If schemas differ in column sets, missing columns are automatically filled with nulls:
diff_schema_combined = pt.concat([df_2023, df_2024])

# 4. Horizontal concatenation
widened = pt.concat([features, targets], how="horizontal")
```

---

<a id="polars-delegation"></a>
### Transparent Polars Verb Delegation

Because `pytae.DataFrame` wraps a native Polars frame, **any native Polars method** not explicitly shadowed by Pytae (such as `.with_columns()`, `.describe()`, `.slice()`, `.fill_null()`, `.pipe()`, `.upsample()`) can be called directly on `pytae.DataFrame`. 

Pytae automatically unwraps arguments to Polars and re-wraps Polars results back into `pytae.DataFrame`, meaning **the Pytae method chain never breaks**:

```python
import polars as pl

# Drop seamlessly into native Polars verbs and continue Pytae chaining
res = (
    df1.join(df2, on="id")  # Native Polars join
    .with_columns(bonus=pl.col("score") * 1.1)  # Native Polars with_columns
    .filter("bonus > 100")  # Pytae filter
    .by("dept")  # Pytae by
    .mutate(avg="mean(bonus)")  # Pytae mutate
    .slice(0, 50)  # Native Polars slice
    .arrange("-avg")  # Pytae arrange
)
```

---

<a id="api-quick-reference"></a>
## I/O API Quick Reference

| Function / Method | Signature | Description |
|:---|:---|:---|
| **`pt.read()`** | `pt.read(path, **kwargs) -> DataFrame` | Eager reader (Parquet, CSV, TSV, DAT, JSONL, Excel, URLs). |
| **`pt.scan()`** | `pt.scan(path, **kwargs) -> DataFrame` | Lazy reader with query pushdown (Parquet, CSV, TSV, JSONL, Arrow). |
| **`pt.DataFrame()`**| `pt.DataFrame(data) -> DataFrame` | Universal container constructor (Polars, Pandas, Arrow, dicts). |
| **`pt.join()`** | `pt.join(left, other, on=None, how='inner', ...) -> DataFrame` | Joins two tabular datasets via Polars multithreading. |
| **`df.join()`** | `df.join(other, on=None, how='inner', ...) -> DataFrame` | Joins this DataFrame with another dataset in a fluent chain. |
| **`pt.concat()`** | `pt.concat(items, how='vertical', ...) -> DataFrame` | Concatenates DataFrames vertically or horizontally. |
| **`df.concat()`** | `df.concat(*others, how='vertical', ...) -> DataFrame` | Concatenates this DataFrame with other DataFrames. |
| **`pt.sample()`** | `pt.sample(data_or_name, n=None, frac=None, seed=None)` | Loads sample dataset by name, or samples rows from DataFrame. |
| **`pt.sample_data`**| `pt.sample_data[name] -> DataFrame` | Mapping of all 21 bundled sample datasets. |
| **`df.sample()`** | `df.sample(n=5, frac=None, seed=None, replace=False)` | Randomly samples rows from DataFrame. |
| **`df.head()`** | `df.head(n=5) -> DataFrame` | Returns first $N$ rows (applies slice pushdown on lazy frames). |
| **`df.tail()`** | `df.tail(n=5) -> DataFrame` | Returns last $N$ rows. |
| **`df.collect()`** | `df.collect(**kwargs) -> DataFrame` | Materializes a lazy execution plan into eager RAM. |
| **`df.lazy()`** | `df.lazy() -> DataFrame` | Converts an eager DataFrame into a lazy execution graph. |
| **`df.to_parquet()`**| `df.to_parquet(path, **kwargs)` | Exports to Parquet (uses streaming `sink_parquet` when lazy). |
| **`df.to_csv()`** | `df.to_csv(path, **kwargs)` | Exports to CSV (uses streaming `sink_csv` when lazy). |
| **`df.to_pandas()`** | `df.to_pandas() -> pd.DataFrame` | Converts to Pandas DataFrame with tracked original indices. |
| **`df.to_polars()`** | `df.to_polars() -> pl.DataFrame` | Returns underlying native Polars DataFrame. |
| **`df.to_clip()`** | `df.to_clip()` | Copies table directly to OS clipboard as TSV without index. |

