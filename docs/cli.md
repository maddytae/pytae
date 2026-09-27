# pytae — CLI Reference & Architecture Hub

The `pytae` CLI provides high-performance command-line data processing for tabular files (`.parquet`, `.csv`, `.txt`, `.dat`, `.jsonl`, `.sas7bdat`). It translates library verbs (`pt.select()`, `pt.qry()`, `pt.mutate()`, `pt.agg_df()`, `pt.group_x()`, `pt.long()`, `pt.wide()`, `pt.sql()`) and CLI-native workflows (schema diffing, multi-file merges, header normalization, batch format conversions) into a fluent command-line pipeline without requiring Python scripts or boilerplate code.

---

## Contents

- [Pipeline Execution Model](#pipeline-model)
- [Dedicated Feature Guides](#feature-guides)
- [Functional Areas at a Glance](#functional-areas)
  - [1. Data Inspection & Metadata](#inspection-metadata)
  - [2. Column Selection & Dropping](#column-selection-dropping)
  - [3. Row Filtering](#row-filtering)
  - [4. Feature Engineering & Mutation](#feature-engineering-mutation)
  - [5. DuckDB SQL Engine](#duckdb-sql-engine)
  - [6. Data Cleaning & Value Replacement](#data-cleaning-value-replacement)
  - [7. Aggregations & Group Operations](#aggregations-group-operations)
  - [8. Reshaping & Cross-Tabulation](#reshaping-cross-tabulation)
  - [9. Dataset & Schema Comparison](#dataset-schema-comparison)
  - [10. File I/O, Compression & Batch Export](#file-io-compression-export)
  - [11. Multi-File Pipelines](#multi-file-pipelines)
- [Master Flag Reference](#flag-reference)
- [Decision Guide: Which Flag Should I Use?](#which-flag)
- [Syntax & Quoting Conventions](#quoting)
- [Sample Datasets](#sample-datasets)

---

<a id="pipeline-model"></a>
<a id="basics"></a>
<a id="getting-started"></a>
## Pipeline Execution Model

The `pytae` CLI executes operations sequentially from left to right as an in-memory pipeline:

1. **Flag Order Is the Pipeline**: Flags are evaluated in the order written. For instance, `-qry ... -select ... -agg_df ...` filters rows first, narrows columns second, and aggregates the remaining columns third.
2. **State Handoff**: Each transformation step passes its resulting DataFrame to the next step.
3. **Execution Modes**:
   - **Single-file mode** (standard): `pytae <path> [operations...] [output]`
   - **Multi-file mode**: `pytae -file "alias1=path1; alias2=path2" -merge ...` (replaces positional path)
4. **Terminal vs Non-Terminal Steps**:
   - Most operations (`-select`, `-qry`, `-mutate`, `-sort_by`, `-head`, `-describe`) produce a modified working DataFrame that can continue chaining.
   - Non-DataFrame inspection flags (`-shape`, `-cols`, `-dtype`, `-nulls`, `-info`, `-meta`, `-diff`) print summary text and terminate the pipeline (allowing only `-o clip` to copy the output).
5. **Output Routing**:
   - By default, the terminal displays the final result on stdout.
   - Add `-o <target>` to write to a file, batch convert alongside the input, or copy to the clipboard (`-o clip`).
   - Add `-out_dir <dir>` to route exported files into a destination directory.

```bash
# Example multi-step pipeline: filter rows -> compute column -> pick subset -> export
pytae sales.parquet \
  -qry "region == 'West', revenue > 1000" \
  -mutate "profit_margin = (revenue - cost) / revenue" \
  -select "order_id,region,revenue,profit_margin" \
  -sort_by "profit_margin desc" \
  -o high_margin_west.parquet
```

---

<a id="feature-guides"></a>
## Dedicated Feature Guides

For in-depth syntax rules, comprehensive parameter tables, corner cases, and terminal output examples, refer to the dedicated feature guides:

| Feature Area | Documentation Guide | Key Flags & Capabilities |
|---|---|---|
| **Inspection & Metadata** | [Inspection & Metadata Guide](cli/inspect.md) | `-head`, `-tail`, `-sample`, `-shape`, `-cols`, `-dtype`, `-nulls`, `-describe`, `-info`, `-meta`, `-pager` |
| **Column Selection** | [Column Selection & Dropping Guide](cli/select_drop.md) | `-select`, `-drop`, slices `a:b`, `contains=`, `startswith=`, `regex=`, `dtype=numeric` |
| **Row Filtering** | [Row Filtering Guide](cli/filter.md) | `-qry`, `-query`, `-dropna`, intervals `[min, max]`, set membership, comparisons |
| **Feature Engineering** | [Mutating & Computing Guide](cli/mutate.md) | `-mutate`, formulas, arithmetic, boolean indicators, `@specs.txt`, functional helpers |
| **SQL Engine** | [DuckDB SQL Engine Guide](cli/sql.md) | `-sql`, querying table `data`, window functions, CTEs, `@query.sql`, zero-copy scan |
| **Data Cleaning** | [Data Cleaning & Value Replacement Guide](cli/clean_replace.md) | `-clean_columns` (strip, squeeze, fill, case, dedupe), `-replace_values`, `-handle_missing`, `-rename` |
| **Aggregations & Grouping** | [Aggregations & Grouping Guide](cli/aggregate.md) | `-by` + `-agg` (group summaries & grand totals), `-group_x` (broadcast transforms) |
| **Reshaping & Matrices** | [Reshaping & Cross-Tabulation Guide](cli/reshape.md) | `-long` (melt), `-wide` (pivot), `-crosstab` (contingency matrix), `-value_counts`, `-unique`, `-sort_by` |
| **Dataset Comparison** | [Dataset & Schema Diffing Guide](cli/diff.md) | `-diff`, shape deltas, column changes, schema drift, null count variations, cell mismatches |
| **File I/O & Compression** | [File I/O, Export, & Compression Guide](cli/export_io.md) | `-o`, `-out_dir`, `.parquet`, `.csv`, `.txt`, `.dat`, `.jsonl`, `.csv.gz`, `.jsonl.gz`, `-progress` |
| **Multi-File Pipelines** | [Multi-File Pipelines Guide](cli/multi_file.md) | `-file`, `-merge` (joins), `-concat` (stacking), cross-file `-sql` |

---

<a id="functional-areas"></a>
## Functional Areas at a Glance

<a id="inspection-metadata"></a>
### 1. Data Inspection & Metadata

Quickly peek at data, inspect dimensions, data types, missing value distribution, and statistical summaries without loading the full file into memory. Zero-scan Parquet metadata reads header/footer metadata instantly.

- **Primary flags**: `-head`, `-tail`, `-sample`, `-shape`, `-cols`, `-dtype`, `-nulls`, `-describe`, `-info`, `-meta`, `-pager`
- **Modifiers**: `-seed`, `-frac`, `-pretty`, `-round`

```bash
pytae data.parquet -head 5           # View first 5 rows
pytae data.parquet -meta             # Sub-millisecond Parquet metadata (codecs, row groups)
pytae data.parquet -nulls desc       # Null counts sorted from most to least
pytae data.parquet -describe -pager  # Paginated statistical summary
```

👉 See the complete guide: **[Inspection & Metadata Guide](cli/inspect.md)**

---

<a id="column-selection-dropping"></a>
### 2. Column Selection & Dropping

Narrow, reorder, or subtract columns using exact names, positional slices, regex, pattern matching, or data type categories.

- **Primary flags**: `-select`, `-drop`
- **Pattern tokens**: `contains=`, `startswith=`, `endswith=`, `regex=`, `dtype=`, `exclude_dtype=`

```bash
pytae data.parquet -select "species,island,body_mass_g"           # Explicit column order
pytae data.parquet -select "species:bill_length_mm"               # Contiguous column slice
pytae data.parquet -select "contains=bill,dtype=numeric"          # Pattern union
pytae data.parquet -drop "sex,island"                             # Drop specific columns
```

👉 See the complete guide: **[Column Selection & Dropping Guide](cli/select_drop.md)**

---

<a id="row-filtering"></a>
### 3. Row Filtering

Filter rows using pytae's ergonomic filter syntax (`-qry`) or pandas' query expressions (`-query`). Supports comparison operators, interval checks, string pattern matches, and list memberships.

- **Primary flags**: `-qry`, `-query`, `-dropna`

```bash
pytae data.parquet -qry "species = 'Adelie', body_mass_g > 3500"  # Keyword filtering
pytae data.parquet -qry "body_mass_g = [3000, 4500]"              # Interval range
pytae data.parquet -query "body_mass_g > 3500 and island == 'Dream'" # Pandas query
```

👉 See the complete guide: **[Row Filtering Guide](cli/filter.md)**

---

<a id="feature-engineering-mutation"></a>
### 4. Feature Engineering & Mutation

Create new columns or overwrite existing ones using arithmetic, boolean expressions, vectorized helpers, or external specification files.

- **Primary flags**: `-mutate`
- **Functional helpers**: `if_else()`, `case_when()`, `coalesce()`, `map()`

```bash
pytae data.parquet -mutate "mass_kg = body_mass_g / 1000"
pytae data.parquet -mutate "tier = if_else(body_mass_g > 4000, 'Heavy', 'Light')"
pytae data.parquet -mutate @features.txt                          # Load specs from file
```

👉 See the complete guide: **[Mutating & Computing Guide](cli/mutate.md)**

---

<a id="duckdb-sql-engine"></a>
### 5. DuckDB SQL Engine

Run ad-hoc ANSI SQL queries directly against tabular datasets using DuckDB. Scans file formats like Parquet and CSV directly with zero-copy execution when placed first in the pipeline.

- **Primary flags**: `-sql`
- **Target table**: The active view is always queryable as table `data`.

```bash
pytae data.parquet -sql "select species, avg(body_mass_g) as avg_mass from data group by species"
pytae data.parquet -sql @query.sql                               # Execute query from file
```

👉 See the complete guide: **[DuckDB SQL Engine Guide](cli/sql.md)**

---

<a id="data-cleaning-value-replacement"></a>
### 6. Data Cleaning & Value Replacement

Standardize messy column headers, substitute cell values, fill missing entries, and rename columns anywhere in the pipeline.

- **Primary flags**: `-clean_columns`, `-replace_values`, `-handle_missing`, `-rename`

```bash
# Clean messy header names (strip, lowercase, replace spaces, deduplicate)
pytae data.parquet -clean_columns "strip,squeeze,strip_special,fill,case=lower,dedupe"

# Replace cell values across columns
pytae data.parquet -replace_values "v='old:new',c='category'"

# Impute missing values (. for text, 0 for numeric)
pytae data.parquet -handle_missing

# Rename columns
pytae data.parquet -rename "old_col:new_col"
```

👉 See the complete guide: **[Data Cleaning & Value Replacement Guide](cli/clean_replace.md)**

---

<a id="aggregations-group-operations"></a>
### 7. Aggregations & Group Operations

Perform automated or explicit group summaries, or append group-level statistics to every individual row without collapsing the table.

- **Primary flags**: `-by` (group columns), `-agg` (aggregation functions / mappings), `-group_x` (broadcast transform)

```bash
pytae data.parquet -by species -agg mean
pytae data.parquet -by species -agg "avg_mass = body_mass_g:mean"
pytae data.parquet -agg mean  # Whole-table grand summary
pytae data.parquet -group_x "group=species,v=body_mass_g,a=mean"  # Broadcast transform
```

👉 See the complete guide: **[Aggregations & Grouping Guide](cli/aggregate.md)**

---

<a id="reshaping-cross-tabulation"></a>
### 8. Reshaping & Cross-Tabulation

Pivot tables from long to wide, melt wide tables to long, generate two-way cross-tabulation matrices, tally value combinations, deduplicate rows, and sort records.

- **Primary flags**: `-long`, `-wide`, `-crosstab`, `-value_counts`, `-unique`, `-sort_by`

```bash
pytae data.parquet -long "c=metric,v=reading"                     # Melt
pytae data.parquet -wide "c=metric,v=reading,a=mean"             # Pivot
pytae data.parquet -crosstab "index=species,columns=island,margins=true"
pytae data.parquet -sort_by "body_mass_g desc"
```

👉 See the complete guide: **[Reshaping & Cross-Tabulation Guide](cli/reshape.md)**

---

<a id="dataset-schema-comparison"></a>
### 9. Dataset & Schema Comparison

Compare the active pipeline table against another dataset file. Generates a structured comparison highlighting row/column count differences, column set changes, schema drift, null count deltas, and cell-level value mismatches.

- **Primary flags**: `-diff`

```bash
pytae file_v1.parquet -diff file_v2.parquet
pytae current.csv -query "status == 'active'" -diff baseline.parquet
```

👉 See the complete guide: **[Dataset & Schema Diffing Guide](cli/diff.md)**

---

<a id="file-io-compression-export"></a>
### 10. File I/O, Compression & Batch Export

Convert datasets between formats, read and write compressed files transparently, direct output to dedicated directories, stream large exports with live progress, or copy tables to the clipboard.

- **Primary flags**: `-o` / `--output`, `-out_dir` / `-od`, `-dlim`, `-encoding`, `-progress`, `-nrows`
- **Supported formats**: `.parquet`, `.csv`, `.txt`, `.dat`, `.jsonl`, `.csv.gz`, `.jsonl.gz`, `.sas7bdat` (read-only)

```bash
pytae data.csv -o data.parquet                                    # Format conversion
pytae data.parquet -o clean.jsonl.gz                              # Compressed JSON Lines
pytae 'raw/*.csv' -o parquet -out_dir converted/                  # Batch convert into folder
pytae huge.csv -o huge.parquet -progress 50000                    # Progress streaming
pytae data.parquet -head 10 -o clip                               # Copy to clipboard
```

👉 See the complete guide: **[File I/O, Export, & Compression Guide](cli/export_io.md)**

---

<a id="multi-file-pipelines"></a>
### 11. Multi-File Pipelines

Load multiple named datasets into a single unified pipeline to perform SQL queries across tables, join on shared or distinct keys, or stack records row-wise.

- **Primary flags**: `-file`, `-merge`, `-concat`

```bash
pytae -file "orders.parquet=o; customers.csv=c" \
      -merge "left=o,right=c,on=customer_id,how=left" \
      -head 5

pytae -file "jan.parquet=m1; feb.parquet=m2" \
      -concat "frames='m1,m2'" \
      -shape
```

👉 See the complete guide: **[Multi-File Pipelines Guide](cli/multi_file.md)**

---

<a id="flag-reference"></a>
## Master Flag Reference

| Flag | Category | Summary | Documentation Guide |
|---|---|---|---|
| `-head [N]` | Inspect | Preview first N rows (default: 5) | [cli/inspect.md](cli/inspect.md) |
| `-tail [N]` | Inspect | Preview last N rows (default: 5) | [cli/inspect.md](cli/inspect.md) |
| `-sample [N]` | Inspect | Preview N random rows (supports `-seed`, `-frac`) | [cli/inspect.md](cli/inspect.md) |
| `-shape` | Inspect | Print `(rows, cols)` dimensions (terminal) | [cli/inspect.md](cli/inspect.md) |
| `-cols [asc\|desc]` | Inspect | List column names (default: file order) | [cli/inspect.md](cli/inspect.md) |
| `-dtype [asc\|desc]` | Inspect | List data types per column | [cli/inspect.md](cli/inspect.md) |
| `-nulls [asc\|desc]` | Inspect | Report null counts per column | [cli/inspect.md](cli/inspect.md) |
| `-describe` | Inspect | Summary statistics (returns DataFrame) | [cli/inspect.md](cli/inspect.md) |
| `-info` | Inspect | Pandas `info()` memory and non-null summary | [cli/inspect.md](cli/inspect.md) |
| `-meta` | Inspect | Zero-scan Parquet metadata (compression, row groups, schema) | [cli/inspect.md](cli/inspect.md) |
| `-pager` | Inspect | Pipe terminal output through `$PAGER` or `less` | [cli/inspect.md](cli/inspect.md) |
| `-pretty` | Inspect | Format output as bordered markdown table | [cli/inspect.md](cli/inspect.md) |
| `-round N` | Inspect | Round floating-point numbers to N decimal places | [cli/inspect.md](cli/inspect.md) |
| `-diff PATH` | Inspect | Compare current frame against another file | [cli/diff.md](cli/diff.md) |
| `-select SPEC` | Select & Filter | Filter and reorder columns by name, slice, regex, or dtype | [cli/select_drop.md](cli/select_drop.md) |
| `-drop COLS` | Select & Filter | Remove specific columns by exact name | [cli/select_drop.md](cli/select_drop.md) |
| `-qry CONDITIONS` | Select & Filter | Filter rows using pytae keyword syntax and intervals | [cli/filter.md](cli/filter.md) |
| `-query EXPR` | Select & Filter | Filter rows using pandas `df.query()` expression | [cli/filter.md](cli/filter.md) |
| `-dropna BOOL` | Select & Filter | Control whether NA keys are dropped in aggregations | [cli/filter.md](cli/filter.md) |
| `-mutate SPEC` | Transform | Create or overwrite columns via formulas / helpers | [cli/mutate.md](cli/mutate.md) |
| `-sql QUERY` | Transform | Execute SQL query via DuckDB against table `data` | [cli/sql.md](cli/sql.md) |
| `-clean_columns SPEC` | Clean | Clean headers (strip, squeeze, strip_special, fill, case, dedupe) | [cli/clean_replace.md](cli/clean_replace.md) |
| `-replace_values SPEC` | Clean | Replace cell values (`v=mapping`, `c=cols`, `exact=bool`) | [cli/clean_replace.md](cli/clean_replace.md) |
| `-handle_missing [FILL]` | Clean | Fill NAs (`.` for object, `0` for numeric, or custom fill) | [cli/clean_replace.md](cli/clean_replace.md) |
| `-rename OLD:NEW,...` | Clean | Rename columns anywhere in pipeline or during export | [cli/clean_replace.md](cli/clean_replace.md) |
| `-by COLS` | Aggregate | Grouping columns for `-agg` and `-group_x` | [cli/aggregate.md](cli/aggregate.md) |
| `-agg [SPEC]` | Aggregate | Aggregate numeric columns (or whole table if `-by` omitted) | [cli/aggregate.md](cli/aggregate.md) |
| `-group_x SPEC` | Aggregate | Broadcast group aggregate column to all rows (`group=`, `v=`, `a=`) | [cli/aggregate.md](cli/aggregate.md) |
| `-long [SPEC]` | Reshape | Melt wide table to long format (`c=`, `v=`) | [cli/reshape.md](cli/reshape.md) |
| `-wide [SPEC]` | Reshape | Pivot long table to wide format (`c=`, `v=`, `a=`) | [cli/reshape.md](cli/reshape.md) |
| `-crosstab SPEC` | Reshape | Two-way cross-tabulation matrix (`index=`, `columns=`) | [cli/reshape.md](cli/reshape.md) |
| `-value_counts` | Reshape | Frequency counts of unique column combinations | [cli/reshape.md](cli/reshape.md) |
| `-unique` | Reshape | Remove duplicate rows | [cli/reshape.md](cli/reshape.md) |
| `-sort_by SPEC` | Reshape | Sort rows by column(s) with optional `asc`/`desc` | [cli/reshape.md](cli/reshape.md) |
| `-file SPEC` | Multi-File | Load multiple named input files (`PATH=ALIAS;...`) | [cli/multi_file.md](cli/multi_file.md) |
| `-merge SPEC` | Multi-File | Join `-file` aliases (`left=`, `right=`, `on=`, `how=`) | [cli/multi_file.md](cli/multi_file.md) |
| `-concat SPEC` | Multi-File | Stack `-file` aliases row-wise (`frames=`) | [cli/multi_file.md](cli/multi_file.md) |
| `-o TARGET` | I/O & Export | Destination file, format (`csv`, `parquet`), or `clip` | [cli/export_io.md](cli/export_io.md) |
| `-out_dir DIR` | I/O & Export | Destination directory for exported files | [cli/export_io.md](cli/export_io.md) |
| `-dlim CHAR` | I/O & Export | Custom delimiter for CSV/TXT/DAT | [cli/export_io.md](cli/export_io.md) |
| `-encoding ENC` | I/O & Export | Character encoding (`utf-8`, `latin-1`, `cp1252`) | [cli/export_io.md](cli/export_io.md) |
| `-progress [N]` | I/O & Export | Display row progress during large file export | [cli/export_io.md](cli/export_io.md) |
| `-nrows N` | I/O & Export | Limit maximum number of rows loaded | [cli/export_io.md](cli/export_io.md) |

---

<a id="which-flag"></a>
<a id="decision-table"></a>
## Decision Guide: Which Flag Should I Use?

| Goal / Task | Recommended Flag | Dedicated Guide |
|---|---|---|
| **Pick or reorder columns** | `-select` | [Column Selection & Dropping](cli/select_drop.md) |
| **Drop specific columns** | `-drop` | [Column Selection & Dropping](cli/select_drop.md) |
| **Rename columns** | `-rename` | [Data Cleaning & Value Replacement](cli/clean_replace.md) |
| **Standardize messy headers** | `-clean_columns` | [Data Cleaning & Value Replacement](cli/clean_replace.md) |
| **Filter rows using expressions** | `-qry` | [Row Filtering](cli/filter.md) |
| **Filter rows using pandas query** | `-query` | [Row Filtering](cli/filter.md) |
| **Compute / mutate columns** | `-mutate` | [Mutating & Computing](cli/mutate.md) |
| **Run SQL queries** | `-sql` | [DuckDB SQL Engine](cli/sql.md) |
| **Replace cell values** | `-replace_values` | [Data Cleaning & Value Replacement](cli/clean_replace.md) |
| **Impute missing values (NA)** | `-handle_missing` | [Data Cleaning & Value Replacement](cli/clean_replace.md) |
| **Group summary** | `-by` + `-agg` | [Aggregations & Grouping](cli/aggregate.md) |
| **Whole-table summary** | `-agg` | [Aggregations & Grouping](cli/aggregate.md) |
| **Append group statistic to rows** | `-group_x` | [Aggregations & Grouping](cli/aggregate.md) |
| **Unpivot / melt (wide → long)** | `-long` | [Reshaping & Cross-Tabulation](cli/reshape.md) |
| **Pivot table (long → wide)** | `-wide` | [Reshaping & Cross-Tabulation](cli/reshape.md) |
| **Contingency matrix / cross-tab** | `-crosstab` | [Reshaping & Cross-Tabulation](cli/reshape.md) |
| **Frequency distribution** | `-value_counts` | [Reshaping & Cross-Tabulation](cli/reshape.md) |
| **Deduplicate rows** | `-unique` | [Reshaping & Cross-Tabulation](cli/reshape.md) |
| **Sort rows** | `-sort_by` | [Reshaping & Cross-Tabulation](cli/reshape.md) |
| **Preview rows** | `-head`, `-tail`, `-sample` | [Inspection & Metadata](cli/inspect.md) |
| **Inspect shape, cols, dtypes, nulls** | `-shape`, `-cols`, `-dtype`, `-nulls`, `-info` | [Inspection & Metadata](cli/inspect.md) |
| **Fast Parquet metadata check** | `-meta` | [Inspection & Metadata](cli/inspect.md) |
| **Compare two datasets** | `-diff` | [Dataset & Schema Diffing](cli/diff.md) |
| **Export / convert file format** | `-o`, `-out_dir` | [File I/O, Export, & Compression](cli/export_io.md) |
| **Join or stack multiple files** | `-file` + `-merge` / `-concat` | [Multi-File Pipelines](cli/multi_file.md) |

---

<a id="conventions-reference"></a>
<a id="quoting"></a>
## Syntax & Quoting Conventions

### 1. Shell Quoting
When arguments contain spaces, special operators, or commas, wrap the entire specification in double quotes `""`:
```bash
pytae data.parquet -select "bill length mm,species"
pytae data.parquet -qry "body_mass_g > 3500, species = 'Adelie'"
```

### 2. Assignment vs Mapping
- **`=` is used for assignment**: Creating columns in `-mutate` (`"mass_kg = body_mass_g / 1000"`) or filtering in `-qry` (`"species = 'Adelie'"`).
- **`:` is used for translation mappings**: Renaming in `-rename` (`"old_name:new_name"`) or replacement mappings in `-replace_values` (`"v='old:new'"`).

### 3. Bracketed Column Names
If a column name contains spaces or special characters inside an expression (`-mutate` or `-sql`), enclose it in square brackets `[col name]` or backticks to prevent shell expansion issues:
```bash
pytae data.parquet -mutate "total = [col a] + [col b]"
pytae data.parquet -sql "select [bill length mm] from data"
```

<a id="pytae-kwargs"></a>
### 4. Standard Reshape Keys: `c=`, `v=`, `a=`
Pytae standardizes parameter roles across `-long`, `-wide`, `-group_x`, and `-replace_values`:
- `c=`: Column dimension role (e.g. `c=metric` in melt/pivot, or `c='col_a,col_b'` for replacement scope).
- `v=`: Value column role (e.g. `v=reading` in melt/pivot, `v=body_mass_g` in broadcast, or `v='old:new'` in replace).
- `a=`: Aggregation function (e.g. `a=mean`, `a=sum`, `a=n`).

---

<a id="sample-datasets"></a>
## Sample Datasets

`pytae` includes bundled sample datasets (`penguins`, `tips`, `titanic`, `diamonds`, `mpg`, `flights`) available via `pytae.sample_data`. You can save any sample dataset as a local file to test CLI commands directly:

```bash
python -c "import pytae; pytae.sample_data['penguins'].to_parquet('penguins.parquet')"
python -c "import pytae; pytae.sample_data['tips'].to_parquet('tips.parquet')"
python -c "import pytae; pytae.sample_data['titanic'].to_parquet('titanic.parquet')"
python -c "import pytae; pytae.sample_data['diamonds'].to_parquet('diamonds.parquet')"
python -c "import pytae; pytae.sample_data['mpg'].to_parquet('mpg.parquet')"
python -c "import pytae; pytae.sample_data['flights'].to_parquet('flights.parquet')"
```

### Quick Commands with Sample Datasets

```bash
# Filter and aggregate
pytae penguins.parquet -qry "species = 'Adelie'" -by species -agg mean

# Two-way cross-tabulation
pytae penguins.parquet -crosstab "index=species,columns=island"

# Broadcast group mean without collapsing rows
pytae tips.parquet -select "day,total_bill,tip" -group_x "group=day,v=tip,a=mean"

# Contingency table with grand totals
pytae titanic.parquet -crosstab "index=pclass,columns=survived,margins=true"

# Aggregate numeric metrics per cut
pytae diamonds.parquet -select "cut,price" -by cut -agg mean

# Sort by numeric column descending
pytae mpg.parquet -select "origin,mpg" -sort_by "mpg desc" -head 5

# Explicit grouping with custom aggregation
pytae flights.parquet -by year -agg "passengers = sum"
```
