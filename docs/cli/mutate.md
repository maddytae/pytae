# CLI Feature Guide: Mutating & Computing Columns

[← Back to CLI Reference Hub](../cli.md)

Compute new columns or overwrite existing columns with mathematical formulas, ratios, boolean indicators, and Pandas expressions using `-mutate`.

---

## Contents

- [Overview & Rules](#overview--rules)
- [Basic Arithmetic & Unit Conversion](#basic-arithmetic--unit-conversion)
- [Defining Multiple Columns](#defining-multiple-columns)
- [Boolean Indicators & Flags](#boolean-indicators--flags)
- [Handling Column Names With Spaces](#handling-column-names-with-spaces)
- [Grouped Mutations (`-by` + `-mutate`)](#grouped-mutations--by--mutate)
- [Loading Specs From a File (`@specs.txt`)](#loading-specs-from-a-file-specstxt)
- [Quoting Syntax Rules](#quoting-syntax-rules)

---

## Overview & Rules

The `-mutate` flag evaluates mathematical and logical expressions using Pandas' evaluation engine.

Syntax:
```bash
pytae data.parquet -mutate "new_col = expression"
```

Key Rules:
1. Column names inside the expression must remain **unquoted** so they resolve as variables: `mass_kg = body_mass_g / 1000`.
2. Wrap column names containing spaces in brackets: `[bmi] = [body mass g] / ([bill length mm] ** 2)`.
3. Separate multiple new column definitions with commas: `"col1 = a + b, col2 = a * 2"`.

---

## Basic Arithmetic & Unit Conversion

Convert penguin body mass from grams to kilograms:

```bash
pytae penguins.parquet \
  -mutate "mass_kg = body_mass_g / 1000" \
  -select "species,body_mass_g,mass_kg" \
  -head 3
```

**Output:**
```text
species  body_mass_g  mass_kg
 Adelie       3750.0     3.75
 Adelie       3800.0     3.80
 Adelie       3250.0     3.25
```

---

## Defining Multiple Columns

Define multiple computed fields in a single `-mutate` invocation:

```bash
pytae penguins.parquet \
  -mutate "mass_kg = body_mass_g / 1000, bill_ratio = bill_length_mm / bill_depth_mm" \
  -select "species,mass_kg,bill_ratio" \
  -round 2 \
  -head 3
```

**Output:**
```text
species  mass_kg  bill_ratio
 Adelie     3.75        2.09
 Adelie     3.80        2.27
 Adelie     3.25        2.24
```

---

## Boolean Indicators & Flags

Create binary flag columns by evaluating boolean comparisons:

```bash
pytae penguins.parquet \
  -mutate "is_heavy = body_mass_g > 4000" \
  -select "species,body_mass_g,is_heavy" \
  -head 3
```

**Output:**
```text
species  body_mass_g  is_heavy
 Adelie       3750.0     False
 Adelie       3800.0     False
 Adelie       3250.0     False
```

---

## Handling Column Names With Spaces

If column names have spaces or hyphens, wrap them in square brackets:

```bash
pytae dataset.csv -mutate "[total weight] = [body mass g] + [extra weight]"
```

---

<a id="grouped-mutations--by--mutate"></a>
## Grouped Mutations (`-by` + `-mutate`)

Compute window transforms and group-level statistics (mean, sum, min, max, median, std, var, row count) broadcast back to every row without collapsing the dataset.

Combine `-by` with `-mutate`:

```bash
# Calculate average tip per day, difference from average, and group sample size
pytae tips.parquet \
  -select "day,total_bill,tip" \
  -by day \
  -mutate "avg_tip = mean(tip), diff = tip - avg_tip, cnt = n" \
  -head 5 \
  -round 2
```

**Output:**
```text
day  total_bill  tip  avg_tip  diff  cnt
Sun       16.99 1.01     3.26 -2.25   76
Sun       10.34 1.66     3.26 -1.60   76
Sun       21.01 3.50     3.26  0.24   76
Sun       23.68 3.31     3.26  0.05   76
Sun       24.59 3.61     3.26  0.35   76
```

### Injected Aggregation Helpers

Within grouped `-mutate` expressions, the following aggregations evaluate per group:
- `mean(col)`, `sum(col)`, `median(col)`, `min(col)`, `max(col)`, `std(col)`, `var(col)`
- `n` or `n()`: Group row count (sample size)

### Multi-Column Grouping and Spaced Columns

Pass multiple grouping columns comma-separated, and use square brackets `[col]` for columns with spaces:

```bash
pytae tips.parquet \
  -select "day,time,total_bill,tip" \
  -rename "total_bill:[total bill]" \
  -by "day,time" \
  -mutate "[avg bill] = mean([total bill]), diff = [total bill] - [avg bill]" \
  -head 5 \
  -round 2
```

### Missing Groups with `-dropna`

By default (`-dropna false`), rows containing `NA` in grouping columns are treated as their own distinct group so that no data is silently discarded. Pass `-dropna true` to exclude `NA` groups from calculation (assigning them `NaN` in the newly created columns):

```bash
# Exclude NA groups from group calculation (they receive NaN)
pytae data.parquet -by category -dropna true -mutate "avg_val = mean(val)"
```

---

## Loading Specs From a File (`@specs.txt`)

For complex pipelines with many engineered features, store expressions in an external text file:

```text
# features.txt
mass_kg = body_mass_g / 1000
bill_ratio = bill_length_mm / bill_depth_mm
flipper_to_mass = flipper_length_mm / mass_kg
```

Run via:
```bash
pytae penguins.parquet -mutate @features.txt -head 5
```

---

## Quoting Syntax Rules

In shell environments:
- Enclose the entire argument in double quotes: `-mutate "..."`.
- Inside the expression, use single quotes `'...'` only for string literals.
- Do NOT quote column names:
  - Correct: `mass_kg = body_mass_g / 1000`
  - Incorrect: `mass_kg = 'body_mass_g' / 1000`
