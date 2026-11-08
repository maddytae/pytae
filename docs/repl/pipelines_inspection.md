# REPL Guide: Pipelines & Non-Destructive Inspection

[← Back to Master Reference](../pytae.md)

This guide covers in-memory pipeline transformations and non-destructive data inspection flags in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [In-Memory Pipeline Transformations](#in-memory-pipeline-transformations)
  - [Full CLI Pipeline Verbs](#full-cli-pipeline-verbs)
  - [Assignment vs. Bare Exploration Semantics](#assignment-vs-bare-exploration-semantics)
- [Non-Destructive Data Inspection](#non-destructive-data-inspection)
  - [Previews (`-head`, `-tail`, `-sample`)](#previews--head--tail--sample)
  - [Metadata (`-shape`, `-cols`, `-schema`, `-dtype`, `-nulls`)](#metadata--shape--cols--schema--dtype--nulls)
  - [Statistical Summaries (`-glimpse`, `-describe`, `-freq`)](#statistical-summaries--glimpse--describe--freq)
  - [Comparing Datasets (`-diff`)](#comparing-datasets--diff)

---

## In-Memory Pipeline Transformations

### Full CLI Pipeline Verbs

All standard Pytae CLI transformation flags operate natively in the REPL with 1:1 syntax parity:

```text
# 1. Filter rows
pytae [df: 344x7]> -filter "species == 'Gentoo' and body_mass_g > 4000"
-> df: 124 rows x 7 cols

# 2. Add or mutate columns
pytae [df: 124x7]> -mutate "mass_kg = body_mass_g / 1000.0, heavy = mass_kg > 4.5"
-> df: 124 rows x 9 cols

# 3. Project or exclude columns
pytae [df: 124x9]> -select "species,island,mass_kg,!heavy"
-> df: 124 rows x 3 cols

# 4. Sort rows
pytae [df: 124x3]> -arrange "mass_kg desc"

# 5. Grouped aggregation
pytae [df: 124x3]> -by island -agg "avg_mass=mass_kg:mean, count=count"
-> df: 1 rows x 3 cols
```

### Assignment vs. Bare Exploration Semantics

Pytae draws a clean distinction between **bare exploratory previews** and **state mutations**:

- **Bare preview (`-pivot ...`, `-filter ...`)**: If executed without variable assignment (`df = ...`) or output redirection (`-o ...`), preview commands like `-pivot` display the formatted table in your terminal for immediate inspection **without altering the shape of the underlying table in memory**.
- **Explicit assignment (`df = df -pivot ...` or `summary = df -pivot ...`)**: Mutates the table in memory and registers a permanent state change.
- **Replay Script Safety**: Bare exploratory previews are preserved in your interactive terminal history, but are automatically excluded from saved replay scripts (`exit -s`) so automated batch scripts only contain true state changes.

---

## Non-Destructive Data Inspection

Non-destructive inspection flags display schema, dimensions, or previews without altering or truncating active tables in memory.

### Previews (`-head`, `-tail`, `-sample`)

```text
pytae> -head 5           # Preview first 5 rows
pytae> -tail 5           # Preview last 5 rows
pytae> -sample 10        # Preview 10 random sample rows
```

### Metadata (`-shape`, `-cols`, `-schema`, `-dtype`, `-nulls`)

```text
# Dimensions (rows, cols)
pytae> -shape
(344, 7)

# Column names in file order
pytae> -cols

# Column names sorted alphabetically
pytae> -cols asc
pytae> -cols desc

# Column names filtered by substring
pytae> -cols mass
body_mass_g

# Full structured breakdown (types, null counts, memory)
pytae> -schema

# Column data types (supports sorting)
pytae> -dtype
pytae> -dtype asc

# Missing value counts per column
pytae> -nulls
```

### Statistical Summaries (`-glimpse`, `-describe`, `-freq`)

```text
# Transposed schema with sample values (matches dplyr::glimpse)
pytae> -glimpse

# Descriptive statistics (mean, std, min, max, quartiles)
pytae> -describe

# Frequency distribution table for categorical column
pytae> -freq species
```

### Comparing Datasets (`-diff`)

Compare two in-memory tables, compare the active dataset against another table, or compare against a saved checkpoint with optional key alignment (`on=...`) and numeric tolerance (`-tol ...`). In alignment with Pytae's CLI standard where all dataset verbs use a leading hyphen, `-diff` requires a single hyphen (bare `diff` is rejected with educational guidance):

```text
# Bare -diff automatically compares active table against latest milestone checkpoint
pytae [orders*]> -diff

# Compare active table against orders_backup
pytae [orders]> -diff orders_backup

# Explicitly compare two loaded tables
pytae> -diff df1 df2

# Compare active table against a saved checkpoint (resolves active table inside snapshot)
pytae [orders]> -diff baseline

# Milestone diffing targeting a specific table in a checkpoint
pytae [orders]> -diff baseline:cust

# Milestone diffing across two checkpoints
pytae> -diff v1:orders v2:orders

# Align rows by primary key before comparing values (reports added/removed keys & mismatched cells)
pytae> -diff df1 df2 on=customer_id

# Target a specific table as left operand
pytae> df1 -diff df2 on=customer_id

# Composite multi-column keys and numeric tolerance
pytae> -diff df1 df2 on="store_id, product_id" -tol 0.001

# Compare active table against a saved checkpoint
pytae [df: 344x7]> -diff snap1 on=id

# Embedded spec syntax (identical to CLI)
pytae> -diff df1 "df2,on=customer_id"
```
