# CLI Feature Guide: Dataset & Schema Diffing

[← Back to Master Reference](../../pytae.md)

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
- [Key-Aware Diffing (`on=key`)](#key-aware-diffing-onkey)
- [Python API (`df.diff` / `pt.diff`)](#python-api-dfdiff--ptdiff)
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

### 6. Numeric Tolerance Threshold (`-tol`)
When comparing floating-point numbers subject to rounding or precision differences, specify an absolute tolerance threshold with `-tol`:

```bash
# Ignore floating point differences smaller than 0.01:
pytae v1.parquet -diff v2.parquet -tol 0.01

# Fine-grained threshold:
pytae v1.parquet -diff v2.parquet -tol 1e-4
```
Differences within the tolerance window are treated as matching cells.

---

## Filtering / Transforming Before Diffing

Because `-diff` runs as part of the pipeline, you can filter or transform the left dataset before diffing:

```bash
# Compare only active records against baseline
pytae incoming.parquet \
  -filter "status == 'ACTIVE'" \
  -select "user_id,email,balance" \
  -diff baseline.parquet
```

---

## Key-Aware Diffing (`on=key`)

When comparing tables where rows may be inserted, deleted, reordered, or filtered, direct positional row matching may fail or report misleading cell differences. Use the `on=` parameter inside `-diff` to align rows by primary or composite keys:

```bash
# Key alignment on a single column:
pytae v1.parquet -diff "v2.parquet,on=id"

# Key alignment with numeric tolerance:
pytae v1.parquet -diff "v2.parquet,on=id,tol=1e-4,rtol=1e-5"

# Composite key alignment:
pytae v1.parquet -diff "v2.parquet,on=customer_id:order_date"
```

**Key Alignment Output:**
```text
Key Alignment (on id):
  Matched keys:    1,420
  + Added in left (2):   [1051, 1052]
  - Removed in left (1): [994]

Values:
  Tolerance: tol=0.0001 (for numeric columns)
  Identical: all cell values match within tolerance.
```

When `on=` is specified:
1. Keys present only in the left or right dataset are identified and reported.
2. Matching keys are aligned directly to compare cell values across common non-key columns, regardless of physical row order.

---

## Python API (`df.diff` / `pt.diff`)

Dataset diffing is also available directly in Python pipelines via `pt.diff()` or `DataFrame.diff()`:

```python
import pytae as pt

left = pt.read_parquet("left.parquet")
right = pt.read_parquet("right.parquet")

# Simple diff
report = left.diff(right)
print(report)

# Key-aware diff with tolerance:
report = pt.diff(left, right, on="id", tol=1e-3)
print(report)

# Or via the pt accessor:
report = df.pt.diff(df_ref, on=["user_id", "date"], tol=0.01)
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
