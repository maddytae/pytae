# CLI Feature Guide: Inspection & Metadata

[← Back to CLI Reference Hub](../cli.md)

Inspect file dimensions, structure, sample rows, statistical distributions, and low-level storage metadata without writing boilerplate Python code.

---

## Contents

- [Overview & Rules](#overview--rules)
- [Zero-Scan Parquet Metadata (`-meta`)](#zero-scan-parquet-metadata--meta)
- [Viewing Rows (`-head`, `-tail`, `-sample`)](#viewing-rows--head--tail--sample)
- [In-Line ASCII Visualizations (`-freq`, `-hist`)](#in-line-ascii-visualizations--freq--hist)
- [Dataset Dimensions (`-shape`)](#dataset-dimensions--shape)
- [Column Names & Ordering (`-cols`)](#column-names--ordering--cols)
- [Data Types & Null Counts (`-dtype`, `-nulls`)](#data-types--null-counts--dtype--nulls)
- [Statistical Summaries (`-describe`, `-info`)](#statistical-summaries--describe--info)
- [Terminal Paging (`-pager`)](#terminal-paging--pager)
- [Display Modifiers (`-pretty`, `-round`)](#display-modifiers--pretty--round)
- [Chaining & Terminal Operation Rules](#chaining--terminal-operation-rules)

---

## Overview & Rules

Inspection flags let you understand a dataset's layout and content instantly from the terminal.

| Flag | Description | Terminal Op? |
|---|---|---|
| `-head [N]` | Print the first N rows (default: 5) | No (returns DataFrame) |
| `-tail [N]` | Print the last N rows (default: 5) | No (returns DataFrame) |
| `-sample [N]` | Print N randomly sampled rows (default: 5) | No (returns DataFrame) |
| `-seed N` | Random seed for `-sample` reproducibility | Modifier for `-sample` |
| `-frac P` | Sample a fraction of rows (e.g. `0.1` for 10%) | Modifier for `-sample` |
| `-freq COL` | Terminal ASCII frequency distribution bar chart | **Yes** (terminal) |
| `-hist COL[:BINS]` | Terminal ASCII numeric histogram with bin intervals | **Yes** (terminal) |
| `-shape` | Print `(rows, cols)` tuple | **Yes** (terminal) |
| `-cols [ORDER]` | Print column names (optional `asc`/`desc` sorts names) | **Yes** (terminal) |
| `-dtype [ORDER]` | Print data types per column | **Yes** (terminal) |
| `-nulls [ORDER]` | Print count of missing / NaN values per column | **Yes** (terminal) |
| `-meta` | Zero-scan Parquet metadata (row groups, compression, schema) | **Yes** (terminal) |
| `-info` | Pandas `info()` memory and non-null summary | **Yes** (terminal) |
| `-glimpse` | Transposed column overview with dtypes and inline sample values | **Yes** (terminal) |
| `-describe` | Pandas `describe()` statistical summary | No (returns DataFrame) |
| `-value_counts` | Group counts across current working columns (pair with `-select`) | No (returns DataFrame) |
| `-pager` | Pipe long outputs through system pager (`$PAGER` or `less`) | Display flag |
| `-pretty` | Render plain tables with bordered markdown formatting | Display flag |
| `-round N` | Round numeric columns to N decimal places | Display flag |

> [!NOTE]
> **Zero-cost header reading**: For formats with file-level headers (`.parquet`, `.sas7bdat`), `-shape`, `-cols`, `-dtype`, and `-head` read strictly from the metadata without loading the entire dataset into memory.

---

## Zero-Scan Parquet Metadata (`-meta`)

Inspect Parquet file internals in sub-milliseconds without scanning table data. Displays file size, Parquet format version, row groups count, column compression codecs, compression ratio, and schema.

```bash
pytae penguins.parquet -meta
```

**Output:**
```text
File: penguins.parquet
File size: 7.8 KB
Format: Parquet (version 2.6)
Rows: 344
Columns: 7
Row groups: 1
Compression: SNAPPY
Uncompressed data size: 5.0 KB
Space saving: -57.6%

Schema:
  #    Column             Type
  ---- -----------------  --------------------
  0    species            large_string
  1    island             large_string
  2    bill_length_mm     double
  3    bill_depth_mm      double
  4    flipper_length_mm  double
  5    body_mass_g        double
  6    sex                large_string
```

Copy metadata summary to clipboard:
```bash
pytae penguins.parquet -meta -o clip
```

---

## Viewing Rows (`-head`, `-tail`, `-sample`)

### First N rows (`-head`)

```bash
pytae penguins.parquet -head 3
```

**Output:**
```text
species    island  bill_length_mm  bill_depth_mm  flipper_length_mm  body_mass_g    sex
 Adelie Torgersen            39.1           18.7              181.0       3750.0   Male
 Adelie Torgersen            39.5           17.4              186.0       3800.0 Female
 Adelie Torgersen            40.3           18.0              195.0       3250.0 Female
```

### Last N rows (`-tail`)

```bash
pytae penguins.parquet -tail 3
```

**Output:**
```text
species island  bill_length_mm  bill_depth_mm  flipper_length_mm  body_mass_g    sex
 Gentoo Biscoe            50.4           15.7              222.0       5750.0   Male
 Gentoo Biscoe            45.2           14.8              212.0       5200.0 Female
 Gentoo Biscoe            49.9           16.1              213.0       5400.0   Male
```

### Random rows with reproducible seed (`-sample`)

```bash
pytae penguins.parquet -sample 3 -seed 42
```

**Output:**
```text
  species island  bill_length_mm  bill_depth_mm  flipper_length_mm  body_mass_g    sex
Chinstrap  Dream            50.9           19.1              196.0       3550.0   Male
Chinstrap  Dream            45.2           17.8              198.0       3950.0 Female
   Gentoo Biscoe            46.5           13.5              210.0       4550.0 Female
```

### Sample a percentage (`-frac`)

```bash
# Sample 1% of the dataset and check row count
pytae penguins.parquet -sample -frac 0.01 -shape
```

**Output:**
```text
(3, 7)
```

---

## In-Line ASCII Visualizations (`-freq`, `-hist`)

Inspect categorical distributions and numeric value distributions directly in the terminal without requiring a graphical display or web browser.

### Frequency Distribution Bars (`-freq COL`)

Prints an ASCII horizontal bar chart showing category counts and percentages:

```bash
pytae penguins.parquet -freq species
```

**Output:**
```text
species
Adelie     152 (44.2%)  ████████████████████████████████████████
Gentoo     124 (36.0%)  ████████████████████████████████
Chinstrap   68 (19.8%)  █████████████████
```

### Numeric Histogram (`-hist COL[:BINS]`)

Computes bin intervals for numeric columns and renders a terminal histogram (defaults to 10 bins; specify `:BINS` to adjust):

```bash
pytae penguins.parquet -hist body_mass_g:8
```

**Output:**
```text
body_mass_g (8 bins)
[2700.0, 3150.0)    64 (18.7%)  ████████████████
[3150.0, 3600.0)    71 (20.8%)  ██████████████████
[3600.0, 4050.0)    65 (19.0%)  ████████████████
[4050.0, 4500.0)    37 (10.8%)  █████████
[4500.0, 4950.0)    36 (10.5%)  █████████
[4950.0, 5400.0)    46 (13.5%)  ███████████
[5400.0, 5850.0)    19  (5.6%)  ████
[5850.0, 6300.0]     4  (1.2%)  █
```

---

## Dataset Dimensions (`-shape`)

Returns `(rows, cols)` tuple:

```bash
pytae penguins.parquet -shape
```

**Output:**
```text
(344, 7)
```

Chain after filtering to count matching rows:

```bash
pytae penguins.parquet -qry "species == 'Gentoo'" -shape
```

**Output:**
```text
(124, 7)
```

---

## Column Names & Ordering (`-cols`)

Print all column names in the order they appear in the file:

```bash
pytae penguins.parquet -cols
```

**Output:**
```text
species
island
bill_length_mm
bill_depth_mm
flipper_length_mm
body_mass_g
sex
```

Sort column names alphabetically with `asc` or `desc`:

```bash
pytae penguins.parquet -cols asc
```

**Output:**
```text
bill_depth_mm
bill_length_mm
body_mass_g
flipper_length_mm
island
sex
species
```

---

## Data Types & Null Counts (`-dtype`, `-nulls`)

### Column Data Types (`-dtype`)

```bash
pytae penguins.parquet -dtype
```

**Output:**
```text
species                  str
island                   str
bill_length_mm       float64
bill_depth_mm        float64
flipper_length_mm    float64
body_mass_g          float64
sex                      str
```

### Missing Value Counts (`-nulls`)

```bash
pytae penguins.parquet -nulls
```

**Output:**
```text
species               0
island                0
bill_length_mm        2
bill_depth_mm         2
flipper_length_mm     2
body_mass_g           2
sex                  11
```

Sort by column name descending:
```bash
pytae penguins.parquet -nulls desc
```

---

## Statistical Summaries (`-describe`, `-info`)

### Five-Number Summary (`-describe`)

Computes count, mean, std, min, percentiles (25%, 50%, 75%), and max for numeric columns:

```bash
pytae penguins.parquet -describe -round 1
```

**Output:**
```text
       bill_length_mm  bill_depth_mm  flipper_length_mm  body_mass_g
count           342.0          342.0              342.0        342.0
mean             43.9           17.2              200.9       4201.8
std               5.5            2.0               14.1        802.0
min              32.1           13.1              172.0       2700.0
25%              39.2           15.6              190.0       3550.0
50%              44.4           17.3              197.0       4050.0
75%              48.5           18.7              213.0       4750.0
max              59.6           21.5              231.0       6300.0
```

Because `-describe` returns a DataFrame, it can be filtered, rounded, or exported:
```bash
pytae penguins.parquet -describe -round 2 -o summary.csv
```

### Technical Info (`-info`)

Prints columns, non-null counts, dtypes, and memory usage:

```bash
pytae penguins.parquet -info
```

### Transposed Summary (`-glimpse`)

Inspired by `dplyr::glimpse()` and Polars, `-glimpse` provides an immediate, transposed view of all columns, displaying row count, column count, dtypes, and an inline preview of first values:

```bash
pytae penguins.parquet -glimpse
```

**Output:**
```text
Rows: 344
Columns: 7
$ species           <str>     'Adelie', 'Adelie', 'Adelie', 'Adelie', 'Adelie...
$ island            <str>     'Torgersen', 'Torgersen', 'Torgersen', 'Torgers...
$ bill_length_mm    <float64> 39.1, 39.5, 40.3, NA, 36.7, 39.3, 38.9, 39.2, 3...
$ bill_depth_mm     <float64> 18.7, 17.4, 18.0, NA, 19.3, 20.6, 17.8, 19.6, 1...
$ flipper_length_mm <float64> 181.0, 186.0, 195.0, NA, 193.0, 190.0, 181.0, 1...
$ body_mass_g       <float64> 3750.0, 3800.0, 3250.0, NA, 3450.0, 3650.0, 362...
$ sex               <str>     'Male', 'Female', 'Female', NA, 'Female', 'Male...
```

> [!TIP]
> Unlike `-head`, which wraps across screen lines when dealing with wide tables (20–100+ columns), `-glimpse` guarantees that every column and its data type fit neatly on one line. It is also available in Python via `df.pt.glimpse()`.

---

## Terminal Paging (`-pager`)

When viewing wide tables or large statistical summaries in the terminal, `-pager` streams the output into your system's pager (`$PAGER` or `less`), allowing keyboard navigation (`j`/`k`, `/` search, `q` to quit):

```bash
pytae wide_dataset.parquet -describe -pager
pytae data.parquet -head 100 -pager
```

---

## Display Modifiers (`-pretty`, `-round`)

### Bordered Tables (`-pretty`)

Renders tables with bordered markdown layout:

```bash
pytae penguins.parquet -head 3 -pretty
```

### Rounding Decimals (`-round`)

Rounds all floating-point numbers across the printed output or clipboard:

```bash
pytae penguins.parquet -agg body_mass_g=mean -round 2
```

---

## Chaining & Terminal Operation Rules

Operations whose output is a scalar, list, or text report cannot have downstream DataFrame operations chained after them.

```bash
# Allowed: -shape or -meta can only be followed by -o clip
pytae penguins.parquet -shape -o clip
pytae penguins.parquet -meta -o clip

# Disallowed: Cannot chain DataFrame verbs off -shape
pytae penguins.parquet -shape -head 3
# Error: -shape does not return a DataFrame/Series, so no flag may follow it
```
