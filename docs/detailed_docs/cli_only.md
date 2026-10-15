# Command Line Features & Modifiers (`cli_only`)

While Pytae's core verb vocabulary (`mutate`, `filter`, `select`, `arrange`, `agg`, `pivot`, `distinct`, `pick`, `reshape`) is 100% symmetrical between Python and the shell, `pytae` CLI provides dedicated terminal superpowers: multi-file joining pipelines, schema diffing, instant metadata inspection, cross-file SQL execution, STDIN auto-piping, batch globbing, and pager integration.

---

## Table of Contents

- [Multi-File Pipelines (`-file`, `-join`, `-concat`)](#multi-file-pipelines)
- [Dataset & Schema Diffing (`-diff`)](#dataset-diffing)
- [Fast Inspection & Zero-Scan Metadata (`-meta`, `-shape`, etc.)](#inspection-and-metadata)
- [In-Pipeline & Cross-File SQL (`-sql`)](#sql-engine)
- [Batch Header Cleaning & Value Replacements (`-clean_replace`)](#batch-cleaning)
- [Unix Pipes & STDIN Auto-Detection](#pipes-and-stdin)
- [Batch Globbing & Output Routing (`-od`)](#batch-globbing)
- [Display Modifiers & System Pager (`-pager`, `-pretty`, `-round`)](#display-modifiers)
- [Shell Autocompletion](#shell-autocompletion)

---

<a id="multi-file-pipelines"></a>
## Multi-File Pipelines (`-file`, `-join`, `-concat`)

While standard commands process a single positional file, `-file` switches `pytae` into multi-file mode:
- Semicolon-separated file mappings declare input aliases: `PATH=ALIAS`.
- Pipelines begin with `-join`, `-concat`, or `-sql`.
- Subsequent flags (`-filter`, `-mutate`, `-select`, `-agg`, `-o`) operate on the combined dataset.

### 1. Joining Datasets (`-join`)
Merge two files (or fold in the running pipeline view `data`):

```bash
# Join orders and users on customer_id
pytae -file "orders.parquet=o; users.csv=u" \
  -join "left=o, right=u, on=customer_id, how=left" \
  -filter "region == 'West'" \
  -head 5
```

#### Differing Join Keys (`left_col:right_col`)
```bash
pytae -file "sales.parquet=s; stores.csv=st" \
  -join "left=s, right=st, on=store_code:id, how=inner" \
  -head 5
```

#### Folding Multiple Files with `data`
Chain multiple joins by referencing the running pipeline result `data`:
```bash
pytae -file "orders.parquet=o; customers.csv=c; items.parquet=i" \
  -join "left=o, right=c, on=customer_id, how=left" \
  -join "left=data, right=i, on=item_id, how=left" \
  -head 10
```

### 2. Row-Wise Stacking (`-concat`)
Stack multiple datasets sharing schemas into a single view:

```bash
pytae -file "sales_2023.parquet=s23; sales_2024.parquet=s24" \
  -concat "s23, s24" \
  -by year \
  -agg "total_revenue = revenue:sum"
```

---

<a id="dataset-diffing"></a>
## Dataset & Schema Diffing (`-diff`)

Compare dimensions, added/removed columns, data type drift, null variations, and cell values against a baseline dataset without writing custom validation scripts:

```bash
pytae v1.parquet -diff v2.parquet
```

**Output:**
```text
Comparing:
  Left (source):  v1.parquet (1000 rows, 12 cols)
  Right (target): v2.parquet (1000 rows, 12 cols)

Shape:
  Rows: 1000 vs 1000 (+0)
  Cols: 12 vs 12 (+0)

Columns:
  + Added in left (1):   legacy_flag
  - Removed in left (1): new_status
  Common (11):       id, name, score, ...

Schema Drift:
  * score: int64 -> float64

Null Counts:
  * score: 0 vs 15 nulls (+15)

Values:
  Mismatches found in 4 cells across common columns.
```

- Filter or transform files before diffing:
  ```bash
  pytae raw.csv -filter "status == 'active'" -diff target.parquet
  ```
- Copy diff report to clipboard: `-diff target.parquet -o clip`

---

<a id="inspection-and-metadata"></a>
## Fast Inspection & Zero-Scan Metadata

Understand dataset schemas, shapes, and distributions instantly:

| Flag | Purpose | Notes |
|:---|:---|:---|
| `-meta` | Zero-scan Parquet metadata | Reads file footer without scanning rows |
| `-shape` | Output `(rows, cols)` | Instant on Parquet and SAS |
| `-cols [ORDER]` | List column names | Optional `asc` or `desc` alphabetical sort |
| `-dtype [ORDER]` | Print column data types | Formatted type table |
| `-nulls [ORDER]` | Print missing / null counts | Identifies incomplete columns |
| `-glimpse` | Transposed schema & sample values | Shows row count, dtypes, and inline values |
| `-describe` | Summary statistics | Mean, std, min, max, percentiles |
| `-head [N]`, `-tail [N]` | Print first / last N rows | Defaults to 5 rows |
| `-sample [N]` | Print N random sample rows | Supports `-seed N` and `-frac P` |

### Zero-Scan Parquet Metadata (`-meta`)
Inspect low-level storage details in milliseconds:
```bash
pytae massive_lake.parquet -meta
```
Displays: file size, format version, number of row groups, column compression codecs, compression ratio, and schema.

---

<a id="sql-engine"></a>
## In-Pipeline & Cross-File SQL (`-sql`)

Pytae integrates the native Polars SQL engine (`SQLContext`) for zero-copy, vectorized SQL execution:

```bash
# Query the current pipeline view as table 'data'
pytae penguins.parquet \
  -sql "SELECT species, island, AVG(body_mass_g) as avg_mass FROM data GROUP BY species, island" \
  -head 5

# Read SQL from file
pytae sales.parquet -sql @report_query.sql -o report.csv
```

### Multi-File SQL Joins
Query declared file aliases directly in SQL:
```bash
pytae -file "orders.parquet=o; users.csv=u" \
  -sql "SELECT o.order_id, u.name, o.amount FROM o JOIN u ON o.user_id = u.id WHERE o.amount > 500" \
  -head 10
```

---

<a id="batch-cleaning"></a>
## Batch Header Cleaning & Value Replacements

Clean messy headers or standardize categorical values across datasets:

```bash
# Sanitize header names
pytae messy.csv -clean_columns "case=lower, fill=_" -o clean.parquet

# Replace values
pytae penguins.parquet -replace_values "Adelie=Adelie Penguin, Male=M" -head 5
```

---

<a id="pipes-and-stdin"></a>
## Unix Pipes & STDIN Auto-Detection

`pytae` automatically detects standard input streams:
```bash
# Pipe directly without typing '-'
cat data.csv | pytae -head 5
curl -s https://example.com/events.jsonl | pytae -fmt jsonl -by status -agg "n=n"
```

---

<a id="batch-globbing"></a>
## Batch Globbing & Output Routing (`-od`)

Batch convert hundreds of files with shell globs:
```bash
# Converts every CSV in raw/ to Parquet in lake/ preserving base filenames
pytae "raw/*.csv" -o parquet -od lake/
```

---

<a id="display-modifiers"></a>
## Display Modifiers & System Pager

- `-pager`: Route tall table output through your system pager (`$PAGER` or `less`) so terminal scrollback is not flooded.
- `-pretty`: Force bordered markdown table formatting.
- `-round N`: Round all floating-point numbers to $N$ decimal places for clean reading:
  ```bash
  pytae penguins.parquet -by species -agg "m = mean(body_mass_g)" -round 2
  ```

---

<a id="shell-autocompletion"></a>
## Shell Autocompletion

Enable tab-completion for flags, sample datasets, and filenames:
```bash
pytae --install-completion
```
Supports `bash`, `zsh`, and `fish`.
