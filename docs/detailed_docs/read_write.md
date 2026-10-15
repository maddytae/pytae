# Data Ingestion, Export, & Compression (`read_write`)

`pytae` provides a unified, high-throughput I/O engine powered by a 100% native multithreaded SIMD Polars core with seamless Apache Arrow memory layouts. Whether working interactively in Python or chaining pipelines in the terminal, reading and writing datasets is fast, format-explicit, and memory-efficient.

---

## Rosetta Stone: Python vs. CLI

| Capability | Python Library (`pytae`) | Command Line (`pytae CLI`) |
|:---|:---|:---|
| **Eager Parquet Read** | `pt.read_parquet("data.parquet")` | `pytae data.parquet` |
| **Eager CSV Read** | `pt.read_csv("data.csv")` | `pytae data.csv` |
| **Lazy Parquet Scan** | `pt.scan_parquet("huge.parquet")` | *(Automatic streaming chunk engine)* |
| **Custom Delimiter** | `pt.read_csv("data.txt", separator="\t")` | `pytae data.txt -dlim "\t"` |
| **Encoding Override** | `pt.read_csv("data.csv", encoding="latin-1")`| `pytae data.csv -encoding latin-1` |
| **Export to Parquet** | `df.to_parquet("clean.parquet")` | `pytae raw.csv -o clean.parquet` |
| **Export Shorthand** | — | `pytae raw.csv -o parquet` *(writes raw.parquet)* |
| **Target Output Dir** | — | `pytae "raw/*.csv" -o parquet -od lake/` |
| **Progress Indicator**| — | `pytae huge.csv -o huge.parquet -progress` |
| **Read STDIN / Pipe** | — | `cat stream.csv \| pytae -head 5` |
| **System Clipboard** | Ingest: `pt.read_clipboard()`<br>Export: `df.to_clip()` | Ingest: `pytae clip -head 5`<br>Export: `pytae data.parquet -o clip` |
| **Join Datasets** | `df1.join(df2, on="id", how="left")` | `pytae -file "a.parquet=a; b.csv=b" -join "left=a,right=b,on=id"` |
| **Stack Datasets** | `pt.concat([df1, df2])` | `pytae -file "a.parquet=a; b.parquet=b" -concat "a,b"` |

---

## Supported Formats Matrix

| Format | Extension | Python Reader | Python Scanner | Python Sink | CLI Read | CLI Write | Compression |
|:---|:---|:---|:---|:---|:---:|:---:|:---|
| **Parquet** | `.parquet`, `.pq` | `pt.read_parquet()` | `pt.scan_parquet()` | `df.to_parquet()` | ✓ | ✓ | Snappy, ZSTD, Gzip |
| **CSV** | `.csv` | `pt.read_csv()` | `pt.scan_csv()` | `df.to_csv()` | ✓ | ✓ | `.gz` (transparent) |
| **Delimited Text** | `.txt`, `.tsv` | `pt.read_csv(sep="\t")` | `pt.scan_csv(sep="\t")` | `df.to_csv(sep="\t")` | ✓ | ✓ | `.gz` (transparent) |
| **Pipe-Delimited** | `.dat` | `pt.read_csv(sep="\|")`| `pt.scan_csv(sep="\|")`| `df.to_csv(sep="\|")` | ✓ | ✓ | `.gz` (transparent) |
| **JSON Lines** | `.jsonl`, `.ndjson` | `pt.read_ndjson()` | `pt.scan_ndjson()` | `df.to_ndjson()` | ✓ | ✓ | `.gz` (transparent) |
| **JSON** | `.json` | `pt.read_json()` | — | `df.to_json()` | ✓ | ✓ | Standard JSON |
| **Arrow IPC** | `.arrow`, `.feather`| `pt.read_ipc()` | `pt.scan_ipc()` | `df.to_ipc()` | ✓ | ✓ | Arrow IPC Streams |
| **Excel** | `.xlsx`, `.xls` | `pt.read_excel()` | — | — | ✓ | — | Calamine / OpenXML |
| **SQL Database** | SQL Query / Table | `pt.read_database()` | — | `df.to_database()` | ✓ | — | ADBC / ConnectorX |
| **SAS Dataset** | `.sas7bdat` | `pd.read_sas()` wrapped | — | — | ✓ | — | Read-only |

---

## Python Reading: Eager Readers vs. Lazy Scanners

Pytae separates file ingestion into two clear paradigms:

```
                    ┌────────────────────────┐
                    │      Source File       │
                    │ (.parquet, .csv, etc.) │
                    └───────────┬────────────┘
                                │
             ┌──────────────────┴──────────────────┐
             ▼                                     ▼
     Eager Readers                         Lazy Scanners
   pt.read_parquet(path)                 pt.scan_parquet(path)
   pt.read_csv(path)                     pt.scan_csv(path)
             │                                     │
             ▼                                     ▼
   Materializes to RAM                     Builds Query Graph
   • Polars SIMD Reader                    • Projection Pushdown (Column Pruning)
   • Immediate row access                  • Predicate Pushdown (Row Skipping)
   • In-memory DataFrame                   • Slice Pushdown (Early Termination)
                                                   │
                                                   ▼
                                         Single .collect()
                                         Only reads what's needed!
```

### 1. Eager Readers (`pt.read_*`)

Load tabular data immediately into memory:

```python
import pytae as pt

# Read Parquet
df_pq = pt.read_parquet("sales.parquet")

# Read CSV with custom separator
df_tsv = pt.read_csv("data.tsv", separator="\t")

# Read NDJSON / Line JSON
df_ndjson = pt.read_ndjson("logs.jsonl")

# Read Excel worksheet
df_excel = pt.read_excel("financials.xlsx", sheet_name="Q4")

# Read from SQL Database connection (ADBC, SQLAlchemy, or connection string)
df_sql = pt.read_database("SELECT user_id, amount FROM orders WHERE amount > 100", connection=conn_uri)
```

### 2. Lazy Scanners (`pt.scan_*`)

Lazy scanners register datasets with Polars' query engine without loading rows into RAM. They return a `pytae.DataFrame` with `is_lazy == True` wrapping a `polars.LazyFrame`:

```python
# Scan multi-gigabyte files with query pushdowns
lazy_df = pt.scan_parquet("massive_orders.parquet")

# Build a fluent query pipeline - ZERO rows read yet!
result = (
    lazy_df
    .filter("region == 'EMEA'")
    .select("order_id", "customer_id", "total_usd")
    .mutate(tax="total_usd * 0.20")
    .arrange("-total_usd")
    .head(10)
    .collect()  # Reads ONLY the 3 columns and top 10 matching rows off disk!
)
```

#### Optimization Pushdowns in Action:
- **Projection Pushdown**: If your pipeline only selects 3 of 100 columns, disk I/O skips the remaining 97 columns completely.
- **Predicate Pushdown**: Parquet statistics and dictionary metadata allow Polars to skip entire row groups that don't match `.filter("region == 'EMEA'")`.
- **Slice Pushdown**: Calling `.head(5)` stops disk reading immediately once 5 matching rows are found.

---

## CLI Reading & Ingestion

The CLI reads positional files or pipes directly from the command line:

```bash
# Ingest and display
pytae penguins.parquet -head 5
pytae customers.csv -dlim "," -head 3

# Transparently read gzip files
pytae server_logs.csv.gz -filter "status == 500" -head 10
```

### Reading from STDIN & Unix Pipes (`-`, `-fmt`)
`pytae` features automatic pipe detection. You can pipe streams into `pytae` without typing an explicit `-`:

```bash
# Direct pipe
cat penguins.csv | pytae -head 5
curl -s https://example.com/events.csv | pytae -by event_type -agg "count=n"

# Force format on extensionless or ambiguous streams
curl -s https://example.com/stream | pytae - -fmt jsonl -by status -agg "n=n"
```

### Ingesting from System Clipboard (`pytae clip`)
Instantly analyze data copied to your clipboard (from Excel, Google Sheets, or web tables):

```bash
# Copy tabular text in Excel, then query immediately in terminal:
pytae clip -head 5
pytae clip -filter "amount > 1000" -by department -agg "total = amount:sum"
```

---

## Writing Data & Sinks

### Python Sinks

Pytae DataFrames support out-of-core streaming exports:

```python
# Write out to Parquet with compression
df.to_parquet("clean_sales.parquet", compression="zstd")

# Write to CSV
df.to_csv("clean_sales.csv")

# Copy directly to system clipboard (paste immediately into Excel / Sheets)
df.to_clip()

# Interop: zero-copy conversion to Polars or Pandas
pl_df = df.to_polars()
pd_df = df.to_pandas()
```

### CLI Export Destinations (`-o`)

Write pipeline results to explicit files or format shorthands:

```bash
# Explicit destination file
pytae penguins.parquet -select "species,island,body_mass_g" -o subset.parquet

# In-place format shorthands (changes extension automatically)
pytae raw.csv -o parquet       # writes raw.parquet
pytae data.parquet -o csv.gz   # writes data.csv.gz

# Export directly to system clipboard
pytae penguins.parquet -head 10 -o clip
```

### Target Output Directory (`-out_dir` / `-od`)

Route converted files into dedicated folders. Pytae creates target folders automatically:

```bash
# Single file export to directory
pytae raw.csv -o parquet -od parquet_lake/

# Batch globbing: convert all CSVs into target directory preserving stem names
pytae "raw/*.csv" -o parquet -od parquet_lake/
```

#### Why use `-od` instead of explicit paths?
1. **Mandatory for Batch / Globs**: Prevents all inputs from overwriting a single file name.
2. **Eliminates Shell Boilerplate**: No need for `basename` or `${f%.*}` parameter expansion in shell scripts.
3. **Compound Extension Stripping**: Converts `data.csv.gz` cleanly to `data.parquet` (instead of `data.csv.parquet`).
4. **Collision Guarding**: Ensures files from different source folders with duplicate names do not silently overwrite.

### Streaming Progress Bars (`-progress [N]`)

When exporting multi-million-row datasets, `-progress` streams in memory-efficient chunks with real-time feedback:

```bash
# Default chunk size (200,000 rows/chunk)
pytae 50m_rows.csv -o 50m_rows.parquet -progress

# Custom chunk size (50,000 rows/chunk)
pytae 50m_rows.csv -o 50m_rows.parquet -progress 50000
```

### Robust Mixed-Type Parquet Export
Messy datasets with mixed types (e.g. string numbers and integers in the same column) cause PyArrow `ArrowInvalid` crashes. Pytae automatically intercepts `ArrowInvalid`, converts mixed columns to clean strings with a descriptive `UserWarning`, and completes the Parquet write safely without crashing.

---

## Joining & Stacking Datasets

### In Python:
```python
# Relational Join
df_orders = pt.read_parquet("orders.parquet")
df_users = pt.read_csv("users.csv")

# Join on matching key
merged = df_orders.join(df_users, on="user_id", how="left")

# Join on differing keys using colon syntax
merged = df_orders.join(df_users, on="customer_id:user_id", how="inner")

# Stack rows across datasets
combined = pt.concat([df_2023, df_2024])
```

### In CLI:
Multi-file joining and stacking in the CLI is powered by `-file`, `-join`, and `-concat`:

```bash
pytae -file "orders.parquet=o; users.csv=u" \
  -join "left=o,right=u,on=user_id,how=left" \
  -head 5
```
*(For complete multi-file CLI syntax and SQL joins, see [CLI Only Guide](cli_only.md#multi-file-pipelines)).*
