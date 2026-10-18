# CLI Feature Guide: Row Filtering & Slicing

[← Back to Master Reference](../../pytae.md)

Filter rows using pytae's ergonomic filter expressions (`-filter`), drop missing rows (`-dropna`), or slice rows (`-head`, `-tail`, `-arrange`).

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
- [Slicing Extreme Rows (`-arrange` + `-head` / `-tail`)](#slicing-extreme-rows--arrange--head--tail)
- [Dropping Missing Values (`-dropna`)](#dropping-missing-values--dropna)
- [Quoting Best Practices](#quoting-best-practices)

---

## Overview & Differences

| Flag | Category | Key Syntax Highlights |
|---|---|---|
| `-filter CONDITIONS` | Row Filter | Comma-separated conditions, intervals `col = [min, max]`, list membership `col = ['a', 'b']`, bracketed spaces `[col name]` |
| `-dropna [COLS]` | Row Filter | Drops rows containing `NaN` (bare for all columns, or comma-separated subset) |
| `-head [LIMIT]`, `-tail [LIMIT]` | Row Slicing | Extract first/last $N$, percentage (`10%`), or with ties (`ties=true`), group-aware with `-by` |

---

## Pytae Filtering (`-filter`)

Pytae's `-filter` simplifies row filtering with clean, human-readable syntax.

### Exact Matching

String values inside `-filter` must be enclosed in single quotes `'value'`:

```bash
pytae penguins.parquet -filter "species = 'Gentoo'" -head 3
```

> [!IMPORTANT]
> **Strict String Quoting Requirement**:
> String literals must always be quoted (e.g. `'Gentoo'`, `'9'`). If an unquoted literal or number is passed when filtering a string column (e.g. `species = Gentoo` or `id = 9` where `id` is a string column), `pytae` raises an explicit error guiding you to quote the string. This prevents silent type coercion and avoids unexpected lexicographical comparison anomalies (such as string `'10'` evaluating as less than string `'9'`).

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

## Slicing Extreme Rows (`-arrange` + `-head` / `-tail`)

Extract top or bottom rows ordered by a specific column by composing `-arrange` with group-aware `-head` or `-tail`. For complete details and syntax, see the [Row Slicing Guide](head_tail.md).

### Top N Rows Overall

```bash
pytae penguins.parquet -arrange "body_mass_g desc" -head 3 -select "species,island,body_mass_g"
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          6300 |
| Gentoo    | Biscoe   |          6050 |
| Gentoo    | Biscoe   |          6000 |

### Bottom N Rows per Group (`-by`)

When combined with `-by`, `-head` and `-tail` extract rows within each unique group:

```bash
pytae penguins.parquet -by species -arrange body_mass_g -head 1 -select "species,body_mass_g"
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
- Enclose string literals in inner single quotes: `'Gentoo'`, `'9'`. Unquoted strings or numbers against string columns will raise an explicit `TypeError`.
- Numeric literals should remain unquoted: `body_mass_g > 3500`.
- Columns with spaces should be wrapped in brackets: `[bill length mm] > 40` or `-arrange "[bill length mm] desc" -head 3`.

