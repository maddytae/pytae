# CLI Feature Guide: Dataset & Schema Diffing

Compare schemas, dimensions, added/removed columns, data type drift, null count variations, and cell values against another tabular dataset using `-diff`.

---

## Contents

- [Overview & Use Cases](#overview--use-cases)
- [Basic Usage](#basic-usage)
- [Detailed Diff Output Breakdown](#detailed-diff-output-breakdown)
  - [1. Shape Comparison](#1-shape-comparison)
  - [2. Column Additions & Removals](#2-column-additions--removals)
  - [3. Schema Drift & Type Changes](#3-schema-drift--type-changes)
  - [4. Null Count Variations](#4-null-count-variations)
  - [5. Value Mismatches Across Matching Rows](#5-value-mismatches-across-matching-rows)
- [Filtering / Transforming Before Diffing](#filtering--transforming-before-diffing)
- [Copying Diff Reports to Clipboard (`-o clip`)](#copying-diff-reports-to-clipboard--o-clip)
- [Batch Diffing Across Multiple Files](#batch-diffing-across-multiple-files)

---

## Overview & Use Cases

Data validation and migration testing frequently require comparing an incoming file against a baseline:
- Did an ETL pipeline drop or rename columns?
- Did an integer column unexpectedly drift into floats or strings?
- Did the null count increase?
- Are the cell values identical between two formats (e.g. parquet vs csv)?

The `-diff` flag conducts these inspections instantly without needing to write custom comparison scripts.

---

## Basic Usage

Compare two datasets directly:

```bash
pytae v1.parquet -diff v2.parquet
```

**Output:**
```text
Comparing:
  Left (source):  v1.parquet (4 rows, 4 cols)
  Right (target): v2.parquet (4 rows, 4 cols)

Shape:
  Rows: 4 vs 4 (+0)
  Cols: 4 vs 4 (+0)

Columns:
  + Added in left (1):   old_status
  - Removed in left (1): new_metric
  Common (3):        id, name, score

Schema Drift:
  None (all common columns have matching dtypes)

Null Counts:
  * score: 1 vs 0 nulls (+1)

Values:
  Mismatches found in 3 cells across common columns.
```

---

## Detailed Diff Output Breakdown

### 1. Shape Comparison
Compares row count and column count between left (source) and right (target), highlighting deltas with signed indicators (`+` / `-`).

### 2. Column Additions & Removals
- `+ Added in left`: Columns present in the source but missing from the target.
- `- Removed in left`: Columns present in the target but absent from the source.
- `Common`: Columns existing in both datasets.

### 3. Schema Drift & Type Changes
Reports any column where data types do not match (e.g. `int64 (right) -> float64 (left)`).

### 4. Null Count Variations
Identifies columns where the number of `NaN` or missing values differs, showing the before-and-after count and delta.

### 5. Value Mismatches Across Matching Rows
When row counts match, pytae compares cell values across all common columns:
- If all values match: `Identical: all cell values match exactly.`
- If discrepancies are found: Reports the total count of mismatched cells.

---

## Filtering / Transforming Before Diffing

Because `-diff` runs as part of the pipeline, you can filter or transform the left dataset before diffing:

```bash
# Compare only active records against baseline
pytae incoming.parquet \
  -qry "status = 'ACTIVE'" \
  -select "user_id,email,balance" \
  -diff baseline.parquet
```

---

## Copying Diff Reports to Clipboard (`-o clip`)

Copy the complete text report to your system clipboard for pasting into pull requests, tickets, or chat:

```bash
pytae v1.parquet -diff v2.parquet -o clip
```

---

## Batch Diffing Across Multiple Files

Compare multiple partitions or daily batch files against a shared reference baseline:

```bash
pytae daily_batches/*.parquet -diff baseline.parquet
```
