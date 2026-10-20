# CLI Feature Guide: Mutating & Computing Columns

[← Back to Master Reference](../../pytae.md)

Compute new columns or overwrite existing columns with mathematical formulas, ratios, boolean indicators, and Pandas expressions using `-mutate`.

---

## Contents

- [Overview & Rules](#overview--rules)
- [Basic Arithmetic & Unit Conversion](#basic-arithmetic--unit-conversion)
- [Defining Multiple Columns](#defining-multiple-columns)
- [Multi-Column Transforms (`(col1, col2) = _ * 2`)](#multi-column-transforms-col1-col2---2)
- [Boolean Indicators & Flags](#boolean-indicators--flags)
- [Conditional Logic with `if_else`](#conditional-logic-with-if_else)
- [Multi-Tiered Branching with `case_when`](#multi-tiered-branching-with-case_when)
- [Value Recoding with `map()`](#value-recoding-with-map)
- [Inline Type Casting (`int(_)`, `float(_)`, `str(_)`)](#inline-type-casting)
- [Window Functions (`first`, `last`, `shift`, `cumsum`)](#window-functions)
- [String Methods & Null Checks](#string-methods--null-checks)
- [Handling Column Names With Spaces](#handling-column-names-with-spaces)
- [Grouped Mutations (`-by` + `-mutate`)](#grouped-mutations--by--mutate)
- [Loading Specs From a File (`@specs.txt`)](#loading-specs-from-a-file-specstxt)
- [Quoting Syntax Rules](#quoting-syntax-rules)

---

## Overview & Rules

The `-mutate` flag evaluates mathematical, logical, and window expressions using Polars' multithreaded SIMD vector engine.

Syntax:
```bash
pytae data.parquet -mutate "new_col = expression"
```

Key Rules:
1. Column names inside the expression must remain **unquoted** so they resolve as variables: `mass_kg = body_mass_g / 1000`.
2. Wrap column names containing spaces in brackets: `[bmi] = [body mass g] / ([bill length mm] ** 2)`.
3. Separate multiple new column definitions with commas: `"col1 = a + b, col2 = a * 2"`.
4. Transform multiple columns at once using `(col1, col2) = expr` with `_` as the current column placeholder.
5. In string expressions, use natural English `or` and `and` without defensive parentheses.

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

| species   |   body_mass_g |   mass_kg |
|:----------|--------------:|----------:|
| Adelie    |          3750 |      3.75 |
| Adelie    |          3800 |      3.8  |
| Adelie    |          3250 |      3.25 |

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

| species   |   mass_kg |   bill_ratio |
|:----------|----------:|-------------:|
| Adelie    |      3.75 |         2.09 |
| Adelie    |      3.8  |         2.27 |
| Adelie    |      3.25 |         2.24 |

---

## Multi-Column Transforms (`(col1, col2) = _ * 2`)

Apply the same formula across multiple columns simultaneously using parentheses `(...)` on the left-hand side and `_` as the placeholder for each matched column (the `pytae` equivalent of R `dplyr::across()`):

```bash
# Convert multiple bill columns in-place from mm to cm
pytae penguins.parquet \
  -mutate "(bill_length_mm, bill_depth_mm) = _ / 10" \
  -select "species,bill_length_mm,bill_depth_mm" \
  -head 3
```

**Output:**

| species   |   bill_length_mm |   bill_depth_mm |
|:----------|-----------------:|----------------:|
| Adelie    |             3.91 |            1.87 |
| Adelie    |             3.95 |            1.74 |
| Adelie    |             4.03 |            1.8  |

### Creating New Columns with a Suffix or Prefix

Attach a suffix after `)` or a prefix before `(` to create new columns instead of overwriting the originals:

```bash
# Creates bill_length_mm_cm and bill_depth_mm_cm
pytae penguins.parquet \
  -mutate "(bill_length_mm, bill_depth_mm)_cm = _ / 10" \
  -select "bill_length_mm,bill_length_mm_cm,bill_depth_mm,bill_depth_mm_cm" \
  -head 3
```

**Output:**

|   bill_length_mm |   bill_length_mm_cm |   bill_depth_mm |   bill_depth_mm_cm |
|-----------------:|--------------------:|----------------:|-------------------:|
|             39.1 |                3.91 |            18.7 |               1.87 |
|             39.5 |                3.95 |            17.4 |               1.74 |
|             40.3 |                4.03 |            18   |               1.8  |

### Using `select()` Predicates Inside `(...)`

Any [`select`](select.md) criteria (`startswith=`, `endswith=`, `contains=`, `regex=`, `dtype=numeric`, or slices `start:end`) can be used inside `(...)`:

```bash
# Scale all columns starting with 'bill_'
pytae penguins.parquet \
  -mutate "(startswith=bill_) = _ / 10" \
  -select "species,bill_length_mm,bill_depth_mm" \
  -head 3
```

**Output:**

| species   |   bill_length_mm |   bill_depth_mm |
|:----------|-----------------:|----------------:|
| Adelie    |             3.91 |            1.87 |
| Adelie    |             3.95 |            1.74 |
| Adelie    |             4.03 |            1.8  |

```bash
# Group-wise z-score standardization across all numeric columns
pytae penguins.parquet \
  -by species \
  -mutate "(dtype=numeric) = (_ - mean(_)) / std(_)" \
  -round 2 \
  -head 3
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             0.12 |            0.29 |               -0.99 |          0.11 | Male   |
| Adelie    | Torgersen |             0.27 |           -0.78 |               -0.19 |          0.22 | Female |
| Adelie    | Torgersen |             0.57 |           -0.28 |                1.25 |         -0.98 | Female |

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

| species   |   body_mass_g | is_heavy   |
|:----------|--------------:|:-----------|
| Adelie    |          3750 | False      |
| Adelie    |          3800 | False      |
| Adelie    |          3250 | False      |

---

<a id="conditional-logic-with-if_else"></a>
## Conditional Logic with `if_else`

Use `if_else(condition, true_val, false_val)` to perform vectorized binary branching.

### Example 1: Assigning Category Labels

Inside the outer double quotes `"-mutate \"...\""`, use single quotes `'...'` for string literals:

```bash
pytae tips.parquet \
  -mutate "generous = if_else(tip > 3.0, 'Yes', 'No')" \
  -select "total_bill,tip,generous" \
  -head 5
```

**Output:**

|   total_bill |   tip | generous   |
|-------------:|------:|:-----------|
|        16.99 |  1.01 | No         |
|        10.34 |  1.66 | No         |
|        21.01 |  3.5  | Yes        |
|        23.68 |  3.31 | Yes        |
|        24.59 |  3.61 | Yes        |

### Example 2: Fallback to an Existing Column or Floor Value

Pass column names (unquoted) or numeric scalars for either branch:

```bash
# Set a tip floor at 2.00, preserving the actual tip if higher
pytae tips.parquet \
  -mutate "adj_tip = if_else(tip < 2.0, 2.0, tip)" \
  -select "total_bill,tip,adj_tip" \
  -head 5
```

**Output:**

|   total_bill |   tip |   adj_tip |
|-------------:|------:|----------:|
|        16.99 |  1.01 |      2    |
|        10.34 |  1.66 |      2    |
|        21.01 |  3.5  |      3.5  |
|        23.68 |  3.31 |      3.31 |
|        24.59 |  3.61 |      3.61 |

### Example 3: Compound Conditions with `and` / `or`

Combine multiple conditions naturally using `and`, `or`, or `&`, `|`:

```bash
pytae tips.parquet \
  -mutate "high_spender = if_else(total_bill > 20 and tip > 3.0, 'High', 'Standard')" \
  -select "total_bill,tip,high_spender" \
  -head 5
```

**Output:**

|   total_bill |   tip | high_spender   |
|-------------:|------:|:---------------|
|        16.99 |  1.01 | Standard       |
|        10.34 |  1.66 | Standard       |
|        21.01 |  3.5  | High           |
|        23.68 |  3.31 | High           |
|        24.59 |  3.61 | High           |

---

<a id="multi-tiered-branching-with-case_when"></a>
## Multi-Tiered Branching with `case_when`

For multiple conditions evaluated in priority order, use `case_when((cond1, val1), (cond2, val2), default=fallback)`:

```bash
pytae tips.parquet \
  -mutate "tier = case_when((total_bill >= 25, 'High'), (total_bill >= 15, 'Medium'), default='Low')" \
  -select "total_bill,tier" \
  -head 6
```

**Output:**

|   total_bill | tier   |
|-------------:|:-------|
|        16.99 | Medium |
|        10.34 | Low    |
|        21.01 | Medium |
|        23.68 | Medium |
|        24.59 | Medium |
|        25.29 | High   |

---

<a id="value-recoding-with-map"></a>
## Value Recoding with `map()`

Recode categorical values via a dictionary lookup executed vectorially in the Polars engine:

```bash
# Two-argument: recode mapped values, preserve unmapped rows intact
pytae penguins.parquet -mutate "code = map(species, {'Adelie': 'AD', 'Gentoo': 'GEN'})" -head 5

# Three-argument with literal fallback: replace unmapped rows with 'Other'
pytae penguins.parquet -mutate "code = map(species, {'Adelie': 'AD'}, 'Other')" -head 5

# Three-argument with column fallback: pull replacement from another column
pytae deals.parquet -mutate "party = map(deal_type, {'Direct': 'DIR'}, broker_code)" -head 5
```

---

<a id="inline-type-casting"></a>
## Inline Type Casting (`int(_)`, `float(_)`, `str(_)`)

Cast column types directly inside `-mutate` using standard constructor functions:

```bash
# Convert individual columns
pytae data.csv -mutate "id = str(id), score = int(score), val = float(val)" -head 5

# Multi-column batch casting with across syntax
pytae data.csv -mutate "(col1, col2, col3) = int(_)" -head 5
```

---

<a id="window-functions"></a>
## Window Functions (`first`, `last`, `shift`, `cumsum`)

When combined with `-by`, window functions compute group-partitioned statistics and drifts:

### 1. Group Baselines & Boundaries (`first`, `last`)
```bash
pytae stocks.parquet \
  -by ticker \
  -mutate "baseline = first(price), drift = price - first(price), final = last(price)" \
  -head 5
```

### 2. Time-Series Shifts, Differences, & Growth (`shift`, `lag`, `lead`)
```bash
pytae stocks.parquet \
  -by ticker \
  -mutate "prev = shift(price, 1), diff = price - shift(price, 1), ret = price / shift(price, 1) - 1" \
  -head 5
```

### 3. Cumulative Running Statistics (`cumsum`, `cummax`, `cummin`)
```bash
pytae sales.parquet \
  -by region \
  -mutate "running_total = amount.cumsum(), peak = amount.cummax()" \
  -head 5
```

---

<a id="string-methods--null-checks"></a>
## String Methods & Null Checks

Vectorized string transforms and missing value predicates execute directly in `-mutate`:
- **String Matching**: `.str.contains('pat')`, `.str.starts_with('pre')`, `.str.ends_with('suf')`
- **String Transformations**: `.str.upper()`, `.str.lower()`, `.str.strip()`, `.str.len()`
- **Null Checks**: `.is_null()`, `.is_not_null()`, `fillna(col, default)`

```bash
pytae penguins.parquet \
  -mutate "species_upper = species.str.upper(), is_gen = species.str.starts_with('Gen'), has_sex = sex.is_not_null()" \
  -head 5
```

---

## Handling Column Names With Spaces

If column names have spaces or hyphens, wrap them in square brackets:

```bash
pytae dataset.csv -mutate "[total weight] = [body mass g] + [extra weight]"
```

**Output:**

| body mass g | extra weight | total weight |
|---:|---:|---:|
| 3000 | 500 | 3500 |
| 4000 | 200 | 4200 |
| 5000 | 300 | 5300 |

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
  -mutate "avg_tip = mean(tip), diff = tip - avg_tip, cnt = count()" \
  -head 5 \
  -round 2
```

**Output:**

| day   |   total_bill |   tip |   avg_tip |   diff |   cnt |
|:------|-------------:|------:|----------:|-------:|------:|
| Sun   |        16.99 |  1.01 |      3.26 |  -2.25 |    76 |
| Sun   |        10.34 |  1.66 |      3.26 |  -1.6  |    76 |
| Sun   |        21.01 |  3.5  |      3.26 |   0.24 |    76 |
| Sun   |        23.68 |  3.31 |      3.26 |   0.05 |    76 |
| Sun   |        24.59 |  3.61 |      3.26 |   0.35 |    76 |

### Injected Aggregation Helpers

Within grouped `-mutate` expressions, the following aggregations evaluate per group:
- `mean(col)`, `sum(col)`, `median(col)`, `min(col)`, `max(col)`, `std(col)`, `var(col)`
- `count()`: Group row count (sample size)

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

**Output:**

| day   | time   |   total bill |   tip |   avg bill |   diff |
|:------|:-------|-------------:|------:|-----------:|-------:|
| Sun   | Dinner |        16.99 |  1.01 |      21.41 |  -4.42 |
| Sun   | Dinner |        10.34 |  1.66 |      21.41 | -11.07 |
| Sun   | Dinner |        21.01 |  3.5  |      21.41 |  -0.4  |
| Sun   | Dinner |        23.68 |  3.31 |      21.41 |   2.27 |
| Sun   | Dinner |        24.59 |  3.61 |      21.41 |   3.18 |

### Missing Groups with `-dropna`

By default, rows containing `NA` in grouping columns are treated as their own distinct group so that no data is silently discarded. Chain `-dropna <col>` to exclude missing groups prior to calculation:

```bash
# Drop rows with NaN in grouping column prior to calculation
pytae penguins.parquet -dropna sex -by sex -mutate "avg_mass = mean(body_mass_g)" -select "sex,body_mass_g,avg_mass" -head 3 -round 1
```

**Output:**

| sex | body_mass_g | avg_mass |
|:---|---:|---:|
| Male | 3750.0 | 4545.7 |
| Female | 3800.0 | 3862.3 |
| Female | 3250.0 | 3862.3 |

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
pytae penguins.parquet -mutate @features.txt -select "species,mass_kg,bill_ratio,flipper_to_mass" -head 5
```

**Output:**

| species   |   mass_kg |   bill_ratio |   flipper_to_mass |
|:----------|----------:|-------------:|------------------:|
| Adelie    |      3.75 |         2.09 |             48.27 |
| Adelie    |      3.8  |         2.27 |             48.95 |
| Adelie    |      3.25 |         2.24 |             60    |
| Adelie    |    nan    |       nan    |            nan    |
| Adelie    |      3.45 |         1.9  |             55.94 |

---

## Quoting Syntax Rules

In shell environments:
- Enclose the entire argument in double quotes: `-mutate "..."`.
- Inside the expression, use single quotes `'...'` for string literals:
  - Example: `-mutate "status = 'active'"`
  - Standard inner single quotes `'...'` define string literals, matching standard SQL.
- Do NOT quote column names:
  - Correct: `mass_kg = body_mass_g / 1000`
  - Incorrect: `mass_kg = 'body_mass_g' / 1000`
