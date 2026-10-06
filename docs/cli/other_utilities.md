# CLI Feature Guide: Other Utilities & Miscellaneous Commands

[← Back to CLI Reference Hub](../cli.md)

Essential utilities, convenience flags, inspection shortcuts, cleaning helpers, multi-file workflows, I/O modifiers, and formatting options that complement core analytical verbs.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Inspection & Summary Flags](#inspection--summary-flags)
  - [Zero-Scan Parquet Metadata (`-meta`)](#zero-scan-parquet-metadata--meta)
  - [Rows, Shape & Overview (`-head`, `-tail`, `-sample`, `-shape`, `-glimpse`, `-info`, `-describe`)](#rows-shape--overview--head--tail--sample--shape--glimpse--info--describe)
  - [Column Names, Data Types & Missing Counts (`-cols`, `-dtype`, `-nulls`)](#column-names-data-types--missing-counts--cols--dtype--nulls)
  - [Distribution & Frequency Analysis (`-value_counts`, `-freq`, `-hist`)](#distribution--frequency-analysis--value_counts--freq--hist)
  - [Dataset & Schema Comparison (`-diff`)](#dataset--schema-comparison--diff)
- [Data Cleaning & Header Standardization](#data-cleaning--header-standardization)
  - [Header Cleaning (`-clean_columns`)](#header-cleaning--clean_columns)
  - [Value Replacement (`-replace_values`)](#value-replacement--replace_values)
  - [Missing Value Imputation (`-handle_missing`)](#missing-value-imputation--handle_missing)
  - [Dropping Missing Values (`-dropna`)](#dropping-missing-values--dropna)
  - [Renaming Columns (`-rename`)](#renaming-columns--rename)
- [Multi-File Pipelines & Operations](#multi-file-pipelines--operations)
  - [Named Inputs (`-file`)](#named-inputs--file)
  - [Merging & Joins (`-merge`)](#merging--joins--merge)
  - [Row Stacking (`-concat`)](#row-stacking--concat)
- [Input / Output & Pipeline Modifiers](#input--output--pipeline-modifiers)
  - [Reading Row Caps (`-nrows`, `-limit`)](#reading-row-caps--nrows--limit)
  - [Delimiters & Encodings (`-dlim`, `-encoding`)](#delimiters--encodings--dlim--encoding)
  - [Exporting & Directory Routing (`-o`, `-out_dir`, `-fmt`)](#exporting--directory-routing--o--out_dir--fmt)
  - [Clipboard Export (`-o clip`)](#clipboard-export--o-clip)
  - [Execution Progress (`-progress`)](#execution-progress--progress)
- [Formatting & Display Modifiers](#formatting--display-modifiers)
  - [Markdown Tables (`-pretty`)](#markdown-tables--pretty)
  - [Rounding Decimals (`-round`)](#rounding-decimals--round)
  - [Interactive Paging (`-pager`)](#interactive-paging--pager)
- [Version & Help Diagnostics](#version--help-diagnostics)

---

## Overview & Quick Reference

| Flag | Category | Syntax / Value | Description |
|---|---|---|---|
| `-head [N]` | Inspection | Integer (default: `5`) | Displays first N rows |
| `-tail [N]` | Inspection | Integer (default: `5`) | Displays last N rows |
| `-sample [N]` | Inspection | Integer (default: `5`) | Displays N randomly sampled rows |
| `-seed N` | Inspection | Integer | Random seed for `-sample` reproducibility |
| `-frac P` | Inspection | Float `0 < P <= 1` | Sample fraction of rows instead of count |
| `-shape` | Inspection | Terminal flag | Prints dataset dimensions `(rows, cols)` |
| `-cols [ORDER]` | Inspection | Optional `asc` or `desc` | Prints column names (file order, or sorted) |
| `-dtype [ORDER]` | Inspection | Optional `asc` or `desc` | Prints column data types |
| `-nulls [ORDER]` | Inspection | Optional `asc` or `desc` | Prints null / NaN count per column |
| `-describe` | Inspection | Flag | Computes summary statistics (count, mean, std, min, max, quartiles) |
| `-info` | Inspection | Flag | Prints pandas memory footprint and non-null counts |
| `-glimpse` | Inspection | Flag | Transposed column overview with dtypes and sample values |
| `-meta` | Inspection | Flag | Instant Parquet metadata (row groups, compression, schema) |
| `-diff PATH` | Inspection | File path | Compares schemas, shapes, column drift, and cell values against another dataset |
| `-value_counts` | Inspection | Flag | Shows frequency counts across current working columns (use with `-select`) |
| `-freq COL` | Inspection | Column name | Renders horizontal ASCII frequency bars with percentages |
| `-hist COL[:BINS]` | Inspection | `col` or `col:bins` | Renders in-terminal ASCII distribution histogram |
| `-clean_columns SPEC` | Cleaning | `strip,fill=_,case=lower,...` | Normalizes messy column header names |
| `-replace_values SPEC` | Cleaning | `old:new` or `c=col,old:new` | Replaces cell values (exact or substring) |
| `-handle_missing [FILL]`| Cleaning | Imputation string (default: `.`) | Fills text NaN with marker, numeric NaN with 0 |
| `-dropna [COLS]` | Cleaning | Optional comma-separated list | Drops rows containing NaN (across all columns or specified subset) |
| `-rename SPEC` | Cleaning | `old:new,...` | Explicitly renames column headers |
| `-file SPEC` | Multi-File | `path=alias;...` | Loads multiple input files into named aliases |
| `-merge SPEC` | Multi-File | `left=a,right=b,on=k,...` | Joins datasets on keys with join validation |
| `-concat SPEC` | Multi-File | `a,b` or `how=outer` | Stacks multiple datasets row-wise |
| `-nrows N` / `-limit N`| Input I/O | Integer | Caps rows loaded from disk during read |
| `-dlim STR` | Input I/O | Character (`","`, `"\t"`, `"|"`) | Delimiter for CSV / text files |
| `-encoding ENC` | Input I/O | Encoding name (`utf-8`, `latin1`) | Character encoding for text files |
| `-fmt FORMAT` | Input I/O | `csv`, `parquet`, `jsonl`, `txt` | Format override when reading STDIN or extensionless files |
| `-o TARGET` | Output I/O | File path, format, or `clip` | Exports result or copies to clipboard |
| `-out_dir DIR` / `-od` | Output I/O | Directory path | Destination directory for exported files |
| `-progress [N]` | Diagnostics | Optional row frequency | Streaming row count progress during read/write |
| `-pretty` | Formatting | Flag | Formats terminal tables with Markdown borders |
| `-round N` | Formatting | Integer decimals | Rounds floating-point numbers to N places |
| `-pager` | Output | Flag | Pipes terminal output through interactive system pager (`less`) |
| `-version` | Meta | Flag | Displays pytae version information and exits |
| `-h` / `--help` | Meta | Flag | Displays usage help |

---

## Inspection & Summary Flags

### Zero-Scan Parquet Metadata (`-meta`)
Reads metadata footers in sub-milliseconds without scanning table data:
```bash
pytae transactions.parquet -meta
```

### Rows, Shape & Overview (`-head`, `-tail`, `-sample`, `-shape`, `-glimpse`, `-info`, `-describe`)
```bash
# Peek at initial or final records
pytae penguins.parquet -head 3
pytae penguins.parquet -tail 3

# Reproducible random sampling
pytae penguins.parquet -sample 5 -seed 42
pytae penguins.parquet -sample -frac 0.05 -seed 42

# Dimensions, memory, and statistical summaries
pytae penguins.parquet -shape
pytae penguins.parquet -glimpse
pytae penguins.parquet -info
pytae penguins.parquet -describe
```

### Column Names, Data Types & Missing Counts (`-cols`, `-dtype`, `-nulls`)
```bash
# Column names in file order or sorted
pytae penguins.parquet -cols
pytae penguins.parquet -cols desc

# Column dtypes
pytae penguins.parquet -dtype

# Null value diagnostics per column
pytae penguins.parquet -nulls desc
```

### Distribution & Frequency Analysis (`-value_counts`, `-freq`, `-hist`)
```bash
# Frequency breakdown of categorical values
pytae penguins.parquet -select "species,island" -value_counts
pytae penguins.parquet -freq species

# Numeric distribution histogram directly in terminal
pytae penguins.parquet -hist body_mass_g
pytae penguins.parquet -hist body_mass_g:12
```

### Dataset & Schema Comparison (`-diff`)
Validates schema drift, shape deltas, added/removed columns, and value mismatches between two files:
```bash
pytae raw_v1.parquet -diff raw_v2.parquet
```

---

## Data Cleaning & Header Standardization

### Header Cleaning (`-clean_columns`)
Standardizes headers in order: `strip` -> `strip_special` -> `squeeze` -> `fill` -> `case` -> `dedupe`:
```bash
pytae messy.csv -clean_columns "strip,strip_special,fill=_,case=lower" -head 3
```

### Value Replacement (`-replace_values`)
Swap cell contents with exact matching or substring matching:
```bash
# Exact replacement across all columns
pytae penguins.parquet -replace_values "Male:M,Female:F" -head 3

# Restrict replacement to specific column
pytae penguins.parquet -replace_values "c=sex,Male:M,Female:F" -head 3

# Substring matching anywhere inside cell
pytae logs.csv -replace_values "exact=false,WARN:WARNING" -head 3
```

### Missing Value Imputation (`-handle_missing`)
Fills text NaN with a visible marker (default `.`) and numeric NaN with `0`:
```bash
pytae penguins.parquet -handle_missing -head 5
pytae penguins.parquet -handle_missing "Unknown" -head 5
```

### Dropping Missing Values (`-dropna`)
```bash
# Drop rows with ANY missing value across all columns
pytae penguins.parquet -dropna

# Drop rows missing specific column values
pytae penguins.parquet -dropna "sex,body_mass_g"
```

### Renaming Columns (`-rename`)
```bash
pytae penguins.parquet -rename "body_mass_g:mass,flipper_length_mm:flipper" -head 3
```

---

## Multi-File Pipelines & Operations

### Named Inputs (`-file`)
Loads multiple files simultaneously into named aliases:
```bash
pytae -file "emp.parquet=emp; dept.csv=dept" -merge "left=emp,right=dept,on=dept_id" -head 5
```

### Merging & Joins (`-merge`)
Performs joins with optional relationship validation:
```bash
pytae -file "sales.parquet=s; stores.parquet=st" \
  -merge "left=s,right=st,on=store_id,how=left,validate=many_to_one" \
  -head 5
```

### Row Stacking (`-concat`)
Stacks two or more datasets vertically:
```bash
pytae -file "q1.parquet=a; q2.parquet=b; q3.parquet=c" -concat "a,b,c" -shape
```

---

## Input / Output & Pipeline Modifiers

### Reading Row Caps (`-nrows`, `-limit`)
Stops reading at disk level after N rows (saving RAM and CPU on huge files):
```bash
pytae huge_log.csv -nrows 1000 -shape
```

### Delimiters & Encodings (`-dlim`, `-encoding`)
```bash
pytae records.dat -dlim "|" -shape
pytae legacy.txt -dlim "\t" -encoding latin1 -head 5
```

### Exporting & Directory Routing (`-o`, `-out_dir`, `-fmt`)
```bash
# Convert to Parquet
pytae input.csv -o output.parquet

# Convert and save in specific folder
pytae input.csv -o parquet -out_dir clean_data/

# Specify input format when reading from STDIN
cat data.jsonl | pytae - -fmt jsonl -shape
```

### Clipboard Export (`-o clip`)
Copies intermediate or final pipeline table to the OS clipboard as clean TSV:
```bash
pytae penguins.parquet -by species -agg "mean=body_mass_g:mean" -o clip
```

### Execution Progress (`-progress`)
Displays streaming row status during reading or exporting large datasets:
```bash
pytae huge_events.csv -progress -o events.parquet
```

---

## Formatting & Display Modifiers

### Markdown Tables (`-pretty`)
Renders formatted ASCII table with Markdown borders (`df.to_markdown()`):
```bash
pytae penguins.parquet -by species -agg mean -pretty
```

### Rounding Decimals (`-round`)
Rounds all numeric columns to N decimals on display:
```bash
pytae penguins.parquet -by species -agg mean -round 2
```

### Interactive Paging (`-pager`)
Pipes output through the terminal pager (`less` / `$PAGER`) to browse wide tables or large summaries:
```bash
pytae penguins.parquet -describe -pager
```

---

## Version & Help Diagnostics

```bash
# Display installed pytae version
pytae -version

# Full command-line flag documentation
pytae -help

# Keyword-focused help with syntax and copy-pasteable examples
pytae -help agg
pytae -help qry
pytae -help mutate
pytae -help select
pytae -help pivot
pytae -help sql
pytae -help reshape
pytae -help arrange
pytae -help slice
pytae -help dedupe
```
