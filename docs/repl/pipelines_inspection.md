# REPL Guide: In-Memory Pipelines & Data Inspection

[← Back to REPL Hub](README.md) | [Master Reference](../pytae.md)

This guide covers in-memory pipeline transformations, assignment vs. exploration semantics, multi-table joins, and non-destructive data inspection tools in the Pytae interactive REPL (`pytae -i`).

---

## Contents

- [The Core Rule: Assignment vs. Bare Exploration](#the-core-rule-assignment-vs-bare-exploration)
  - [Bare Exploratory Previews (Non-Mutating)](#bare-exploratory-previews-non-mutating)
  - [State Mutation via Explicit Assignment](#state-mutation-via-explicit-assignment)
  - [Assigning Results to New Tables](#assigning-results-to-new-tables)
- [In-Memory Pipeline Verbs](#in-memory-pipeline-verbs)
  - [Chaining Multiple Verbs](#chaining-multiple-verbs)
  - [Multi-Line Pipeline Continuation (`\`)](#multi-line-pipeline-continuation-)
- [Multi-Table Operations](#multi-table-operations)
  - [Relational Joins (`-join`)](#relational-joins--join)
  - [Table Concatenation (`-concat`)](#table-concatenation--concat)
- [Non-Destructive Data Inspection](#non-destructive-data-inspection)
  - [Previews (`-head`, `-tail`, `-sample`)](#previews--head--tail--sample)
  - [Structural Inspection (`-schema`, `-cols`, `-dtype`, `-shape`, `-nulls`)](#structural-inspection--schema--cols--dtype--shape--nulls)
  - [Statistical Summaries (`-glimpse`, `-describe`, `-freq`)](#statistical-summaries--glimpse--describe--freq)
  - [Terminal Visualizations (`-bar`, `-scatter`, `-hist`, `-corr`)](#terminal-visualizations--bar--scatter--hist--corr)
  - [Comparing Datasets (`-diff`)](#comparing-datasets--diff)

---

## The Core Rule: Assignment vs. Bare Exploration

In Pytae, the interactive shell follows an ironclad rule: **Bare verbs never mutate your data**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              THE PYTAE SAFETY CONTRACT                                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  pytae> -filter "amount > 100"       # SAFE: Previews filtered rows. Table untouched.  │
│  pytae> df = -filter "amount > 100"  # EXPLICIT: Table 'df' updated in RAM.           │
│  pytae> big = -filter "amount > 100" # DERIVED: Creates new table 'big' in RAM.       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Bare Exploratory Previews (Non-Mutating)

Running a verb directly against the prompt computes and renders an immediate terminal preview without altering the underlying table in memory:

```text
pytae [df: 344x7]> -filter "species == 'Gentoo' and body_mass_g > 5000"
shape: (61, 7)
┌─────────┬───────────┬────────────────┬───────────────┬───────────────────┬─────────────┬────────┐
│ species ┆ island    ┆ bill_length_mm ┆ bill_depth_mm ┆ flipper_length_mm ┆ body_mass_g ┆ sex    │
│ ---     ┆ ---       ┆ ---            ┆ ---           ┆ ---               ┆ ---         ┆ ---    │
│ str     ┆ str       ┆ f64            ┆ f64           ┆ i64               ┆ i64         ┆ str    │
╞═════════╪═══════════╪════════════════╪═══════════════╪═══════════════════╪═════════════╪════════╡
│ Gentoo  ┆ Biscoe    ┆ 46.1           ┆ 13.2          ┆ 211               ┆ 5300        ┆ female │
│ Gentoo  ┆ Biscoe    ┆ 50.0           ┆ 16.3          ┆ 230               ┆ 5700        ┆ male   │
└─────────┴───────────┴────────────────┴───────────────┴───────────────────┴─────────────┴────────┘

# Notice: The active table dimension remains 344x7!
pytae [df: 344x7]> 
```

### State Mutation via Explicit Assignment

To persist transformations, assign the pipeline result back to the table:

```text
pytae [df: 344x7]> df = -filter "species in ['Adelie', 'Gentoo'] and body_mass_g >= 3500"
Updated 'df' (188 rows x 7 cols).

pytae [df: 188x7]> df = -mutate "mass_kg = body_mass_g / 1000" -select "species,island,mass_kg"
Updated 'df' (188 rows x 3 cols).

pytae [df: 188x3]> 
```

### Assigning Results to New Tables

Create derived tables without modifying the original source:

```text
pytae [orders, cust]> big_orders = orders -filter "total > 500"
Created 'big_orders' (12,400 rows x 6 cols).

# Both 'orders' and 'big_orders' now exist independently in memory
pytae [orders, cust, big_orders]> 
```

---

## In-Memory Pipeline Verbs

All 19 Pytae CLI flags execute at native Polars multithreaded SIMD speeds directly inside the REPL.

### Chaining Multiple Verbs

Chain verbs from left to right as a continuous pipeline:

```text
pytae [penguins]> -filter "body_mass_g > 3500" \
                  -mutate "mass_kg = body_mass_g / 1000" \
                  -by species,island \
                  -agg "n=count, avg_mass=mass_kg:mean" \
                  -arrange "avg_mass desc"
```

### Multi-Line Pipeline Continuation (`\`)

For long or complex transformation chains, terminate lines with a backslash `\` to continue input:

```text
pytae [df: 10,000x8]> df = -filter "status == 'completed'" \
                      -mutate "margin = revenue - cost" \
                      -arrange "margin desc" \
                      -head 10
Updated 'df' (10 rows x 9 cols).
```

If you make a mistake while constructing a multi-line buffer, press <kbd>Ctrl+C</kbd> to discard the buffer and return to an empty prompt.

---

## Multi-Table Operations

### Relational Joins (`-join`)

Perform in-memory relational joins across loaded tables:

```text
# Left join 'cust' into active table 'orders' on customer_id
pytae [orders, cust]> orders -join cust on=customer_id how=left

# Join on differing column names
pytae [orders, cust]> orders -join cust on=cust_id:id how=inner

# Assign join result to a new table
pytae [orders, cust]> enriched = orders -join cust on=customer_id
Created 'enriched' (100,000 rows x 10 cols).

# Join and export directly to file in one step
pytae [orders, cust]> orders -join cust on=customer_id -o merged.parquet
Exported 100,000 rows to merged.parquet.
```

Supported join types: `how=left`, `how=inner`, `how=outer`, `how=semi`, `how=anti`, `how=cross`.

### Table Concatenation (`-concat`)

Concatenate tables vertically (row-bind) or horizontally (column-bind):

```text
# Vertical union
pytae [q1, q2]> all_sales = -concat "tables=q1,q2, how=vertical"
```

---

## Non-Destructive Data Inspection

Pytae provides a comprehensive suite of inspection tools that never alter your underlying data.

### Previews (`-head`, `-tail`, `-sample`, `-browse`)

```text
# Preview first 5 rows
pytae [df: 344x7]> -head 5

# Preview last 10 rows
pytae [df: 344x7]> -tail 10

# Interactive full-screen terminal grid browser with live sorting and sticky headers
pytae [df: 344x7]> -browse
# Controls: arrow keys / vi keys (h/j/k/l), s (toggle sort column/direction), ? (help), q (exit)

# Deterministic random sample (percentage or row count)
pytae [df: 344x7]> -sample 10% -seed 42
pytae [df: 344x7]> -sample 50
```

### Structural Inspection (`-schema`, `-cols`, `-dtype`, `-shape`, `-nulls`)

```text
# Comprehensive schema breakdown (types, null %, unique counts)
pytae [df: 344x7]> -schema

# Column names list
pytae [df: 344x7]> -cols

# Column names sorted alphabetically
pytae [df: 344x7]> -cols asc

# Column data types
pytae [df: 344x7]> -dtype

# Dimensions (rows, cols)
pytae [df: 344x7]> -shape
(344, 7)

# Missing value audit across all columns
pytae [df: 344x7]> -nulls
```

### Statistical Summaries (`-glimpse`, `-describe`, `-freq`)

```text
# Transposed overview showing data types and first values
pytae [df: 344x7]> -glimpse

# Five-number summary (mean, std, min, 25%, 50%, 75%, max)
pytae [df: 344x7]> -describe

# Frequency distribution table for categorical columns
pytae [df: 344x7]> -freq species
┌───────────┬───────┬─────────┐
│ species   ┆ count ┆ percent │
│ ---       ┆ ---   ┆ ---     │
│ str       ┆ i64   ┆ f64     │
╞═══════════╪═══════╪═════════╡
│ Adelie    ┆ 152   ┆ 44.19   │
│ Gentoo    ┆ 124   ┆ 36.05   │
│ Chinstrap ┆ 68    ┆ 19.77   │
└───────────┴───────┴─────────┘
```

### Terminal Visualizations (`-bar`, `-scatter`, `-hist`, `-corr`)

Generate instant Unicode ASCII charts directly in your terminal:

```text
# Frequency bar chart
pytae [df: 344x7]> -freq species -bar

# Histogram distribution of a continuous column
pytae [df: 344x7]> df -hist body_mass_g

# Correlation matrix
pytae [df: 344x7]> -corr
```

### Comparing Datasets (`-diff`)

Compare active tables against other tables or saved checkpoints:

```text
# Compare active table against another loaded table
pytae [today, yesterday]> -diff yesterday on=id tol=1e-4

# Compare active table against latest milestone checkpoint
pytae [df*]> -diff baseline
```
