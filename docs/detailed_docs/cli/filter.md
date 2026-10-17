# CLI Feature Guide: Row Filtering & Slicing

[← Back to Master Reference](../../pytae.md)

Filter rows using pytae's ergonomic filter expressions (`-filter`), drop missing rows (`-dropna`), or extract extreme rows (`-pick`).

---

## Contents

- [Overview & Differences](#overview--differences)
- [Pytae Filtering (`-filter`)](#pytae-filtering--filter)
  - [Exact Matching](#exact-matching)
  - [Comparisons (`>`, `<`, `>=`, `<=`, `!=`)](#comparisons)
  - [Intervals & Ranges (`[start, end]`)](#intervals--ranges)
  - [List Membership (`['a', 'b']`)](#list-membership)
  - [Filtering Non-Missing Values (`notna`) & Columns with Spaces](#filtering-non-missing-values-notna--columns-with-spaces)
  - [Combining Multiple Conditions](#combining-multiple-conditions)
- [Selecting Extreme Rows (`-pick`)](#selecting-extreme-rows--pick)
- [Dropping Missing Values (`-dropna`)](#dropping-missing-values--dropna)
- [Quoting Best Practices](#quoting-best-practices)

---

## Overview & Differences

| Flag | Category | Key Syntax Highlights |
|---|---|---|
| `-filter CONDITIONS` | Row Filter | Comma-separated conditions, intervals `col = [min, max]`, list membership `col = ['a', 'b']`, bracketed spaces `[col name]` |
| `-dropna [COLS]` | Row Filter | Drops rows containing `NaN` (bare for all columns, or comma-separated subset) |
| `-pick SPEC` | Row Slicing | Select top/bottom rows by column (`col,n=N` or `col,order=min`), group-aware with `-by` |

---

## Pytae Filtering (`-filter`)

Pytae's `-filter` simplifies row filtering with clean, human-readable syntax.

### Exact Matching

String values inside `-filter` must be enclosed in single quotes `'value'`:

```bash
pytae penguins.parquet -filter "species = 'Gentoo'" -head 3
```

**Output:**

| species   | island   |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:---------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Gentoo    | Biscoe   |             46.1 |            13.2 |                 211 |          4500 | Female |
| Gentoo    | Biscoe   |             50   |            16.3 |                 230 |          5700 | Male   |
| Gentoo    | Biscoe   |             48.7 |            14.1 |                 210 |          4450 | Female |

<a id="comparisons"></a>
### Comparisons (`>`, `<`, `>=`, `<=`, `!=`)

```bash
pytae penguins.parquet -filter "body_mass_g > 5500" -select "species,island,body_mass_g" -head 3
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          5700 |
| Gentoo    | Biscoe   |          5700 |
| Gentoo    | Biscoe   |          5550 |

### Intervals & Ranges (`[start, end]`)

Pytae provides a concise interval syntax `col = [min, max]` to filter inclusive ranges without repeating the column name:

```bash
pytae penguins.parquet -filter "body_mass_g = [3000, 3200]" -select "species,body_mass_g" -head 3
```

**Output:**

| species   |   body_mass_g |
|:----------|--------------:|
| Adelie    |          3200 |
| Adelie    |          3200 |
| Adelie    |          3000 |

### List Membership (`['a', 'b']`)

Match against a set of candidate values:

```bash
pytae penguins.parquet -filter "species = ['Chinstrap', 'Gentoo']" -select "species,island" -head 3
```

**Output:**

| species   | island   |
|:----------|:---------|
| Chinstrap | Dream    |
| Chinstrap | Dream    |
| Chinstrap | Dream    |

### Filtering Non-Missing Values (`notna`) & Columns with Spaces

To filter for non-missing (`notna` / `is not null`) values on a column whose name contains spaces, enclose the column name in brackets `[col name]`:

```bash
# 1. Bracket method notation
pytae penguins.parquet -rename "bill_length_mm:[bill length mm]" -filter "[bill length mm].notna()" -select "species,[bill length mm]" -head 3

# 2. SQL-style syntax
pytae penguins.parquet -rename "bill_length_mm:[bill length mm]" -filter "[bill length mm] is not null" -select "species,[bill length mm]" -head 3

# 3. Direct inequality check
pytae penguins.parquet -rename "bill_length_mm:[bill length mm]" -filter "[bill length mm] != None" -select "species,[bill length mm]" -head 3
```

**Output:**

| species   |   bill length mm |
|:----------|-----------------:|
| Adelie    |             39.1 |
| Adelie    |             39.5 |
| Adelie    |             40.3 |

### Combining Multiple Conditions

Separate independent conditions with commas (evaluated as logical **AND**):

```bash
pytae penguins.parquet \
  -filter "species = 'Gentoo', body_mass_g > 5500, island = 'Biscoe'" \
  -select "species,body_mass_g,sex" \
  -head 3
```

**Output:**

| species   |   body_mass_g | sex   |
|:----------|--------------:|:------|
| Gentoo    |          5700 | Male  |
| Gentoo    |          5700 | Male  |
| Gentoo    |          5550 | Male  |

---

## Selecting Extreme Rows (`-pick`)

Extract top or bottom rows ordered by a specific column using `-pick`. Fully group-aware when combined with `-by`. For complete details and syntax, see the [Row Picking Guide](pick.md).

Supported specification formats:
- Top rows: `col,n=N` (e.g. `body_mass_g,n=3`)
- Bottom rows: `col,n=N,order=min` (e.g. `body_mass_g,n=1,order=min`)
- Proportion: `col,prop=P` (e.g. `body_mass_g,prop=0.1`)
- Default `n=1, order=max` if `n` and `prop` are omitted (e.g. `body_mass_g`)
- Bracketed notation `[col with spaces],n=N` is supported.

### Top N Rows Overall

```bash
pytae penguins.parquet -pick "body_mass_g,n=3" -select "species,island,body_mass_g"
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          6300 |
| Gentoo    | Biscoe   |          6050 |
| Gentoo    | Biscoe   |          6000 |

### Bottom N Rows per Group (`-by`)

When combined with `-by`, `-pick` extracts rows within each unique group:

```bash
pytae penguins.parquet -by species -pick "body_mass_g,n=1,order=min" -select "species,body_mass_g"
```

**Output:**

| species   |   body_mass_g |
|:----------|--------------:|
| Adelie    |          2850 |
| Chinstrap |          2700 |
| Gentoo    |          3950 |

---

## Dropping Missing Values (`-dropna`)

Drop rows with missing values (`NaN`). Can be run bare or scoped to a comma-separated column list:

```bash
# Drop rows with NaN in any column
pytae penguins.parquet -dropna -head 3
```

**Output:**

| species | island | bill_length_mm | bill_depth_mm | flipper_length_mm | body_mass_g | sex |
|:---|:---|---:|---:|---:|---:|:---|
| Adelie | Torgersen | 39.1 | 18.7 | 181.0 | 3750.0 | Male |
| Adelie | Torgersen | 39.5 | 17.4 | 186.0 | 3800.0 | Female |
| Adelie | Torgersen | 40.3 | 18.0 | 195.0 | 3250.0 | Female |

```bash
# Drop rows with NaN in specific column(s)
pytae penguins.parquet -dropna "body_mass_g,sex" -head 3
```

**Output:**

| species | island | bill_length_mm | bill_depth_mm | flipper_length_mm | body_mass_g | sex |
|:---|:---|---:|---:|---:|---:|:---|
| Adelie | Torgersen | 39.1 | 18.7 | 181.0 | 3750.0 | Male |
| Adelie | Torgersen | 39.5 | 17.4 | 186.0 | 3800.0 | Female |
| Adelie | Torgersen | 40.3 | 18.0 | 195.0 | 3250.0 | Female |

> [!NOTE]
> For scoped aggregations and pivot tables, pass `dropna=true` inside the operation's spec (e.g., `-agg "a=mean,dropna=true"` or `-pivot "r=species,c=sex,dropna=true"`).

---

## Quoting Best Practices

In terminal shells (bash, zsh):
- Enclose the entire spec in outer double quotes: `-filter "..."`.
- Enclose string literals in inner single quotes: `'Gentoo'`.
- Columns with spaces should be wrapped in brackets: `[bill length mm] > 40` or `-pick "[bill length mm],n=3"`.

