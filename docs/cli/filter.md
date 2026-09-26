# CLI Feature Guide: Row Filtering

Filter rows using pytae's ergonomic filter expressions (`-qry`) or standard Pandas query syntax (`-query`).

---

## Contents

- [Overview & Differences](#overview--differences)
- [Pytae Filtering (`-qry`)](#pytae-filtering--qry)
  - [Exact Matching](#exact-matching)
  - [Comparisons (`>`, `<`, `>=`, `<=`, `!=`)](#comparisons)
  - [Intervals & Ranges (`[start, end]`)](#intervals--ranges)
  - [List Membership (`['a', 'b']`)](#list-membership)
  - [Combining Multiple Conditions](#combining-multiple-conditions)
- [Pandas Query Expressions (`-query`)](#pandas-query-expressions--query)
- [Filtering Missing Values (`-dropna`)](#filtering-missing-values--dropna)
- [Quoting Best Practices](#quoting-best-practices)

---

## Overview & Differences

| Flag | Engine | Key Syntax Highlights |
|---|---|---|
| `-qry CONDITIONS` | Pytae `pt.qry()` | Comma-separated conditions, intervals `col = [min, max]`, list membership `col = ['a', 'b']`, handles special characters safely |
| `-query EXPR` | Pandas `df.query()` | Boolean expression string passed to `numexpr` (`col > 10 and other == 'x'`) |
| `-dropna BOOL` | Pandas NA drop | Controls whether null/NaN keys are dropped in aggregations |

---

## Pytae Filtering (`-qry`)

Pytae's `-qry` simplifies row filtering with clean, human-readable syntax.

### Exact Matching

String values inside `-qry` must be enclosed in single quotes `'value'`:

```bash
pytae penguins.parquet -qry "species = 'Gentoo'" -head 3
```

**Output:**
```text
species island  bill_length_mm  bill_depth_mm  flipper_length_mm  body_mass_g    sex
 Gentoo Biscoe            46.1           13.2              211.0       4500.0 Female
 Gentoo Biscoe            50.0           16.3              230.0       5700.0   Male
 Gentoo Biscoe            48.7           14.1              210.0       4450.0 Female
```

### Comparisons (`>`, `<`, `>=`, `<=`, `!=`)

```bash
pytae penguins.parquet -qry "body_mass_g > 5500" -select "species,island,body_mass_g" -head 3
```

**Output:**
```text
species island  body_mass_g
 Gentoo Biscoe       5700.0
 Gentoo Biscoe       5700.0
 Gentoo Biscoe       5550.0
```

### Intervals & Ranges (`[start, end]`)

Pytae provides a concise interval syntax `col = [min, max]` to filter inclusive ranges without repeating the column name:

```bash
pytae penguins.parquet -qry "body_mass_g = [3000, 3200]" -select "species,body_mass_g" -head 3
```

**Output:**
```text
species  body_mass_g
 Adelie       3200.0
 Adelie       3200.0
 Adelie       3000.0
```

### List Membership (`['a', 'b']`)

Match against a set of candidate values:

```bash
pytae penguins.parquet -qry "species = ['Chinstrap', 'Gentoo']" -select "species,island" -head 3
```

**Output:**
```text
  species island
Chinstrap  Dream
Chinstrap  Dream
Chinstrap  Dream
```

### Combining Multiple Conditions

Separate independent conditions with commas (evaluated as logical **AND**):

```bash
pytae penguins.parquet \
  -qry "species = 'Gentoo', body_mass_g > 5500, island = 'Biscoe'" \
  -select "species,body_mass_g,sex" \
  -head 3
```

**Output:**
```text
species  body_mass_g    sex
 Gentoo       5700.0   Male
 Gentoo       5700.0   Male
 Gentoo       5550.0   Male
```

---

## Pandas Query Expressions (`-query`)

Pass arbitrary Pandas boolean expressions directly via `-query`:

```bash
pytae penguins.parquet \
  -query "body_mass_g > 5500 and sex == 'Male'" \
  -select "species,body_mass_g,sex" \
  -head 3
```

**Output:**
```text
species  body_mass_g  sex
 Gentoo       5700.0 Male
 Gentoo       5700.0 Male
 Gentoo       5550.0 Male
```

---

## Filtering Missing Values (`-dropna`)

Pass `-dropna false` to keep NA keys in groupings or aggregations:

```bash
pytae penguins.parquet -agg_df mean -dropna false
```

---

## Quoting Best Practices

In terminal shells (bash, zsh):
- Enclose the entire spec in outer double quotes: `-qry "..."`.
- Enclose string literals in inner single quotes: `'Gentoo'`.
- Columns with spaces should be wrapped in brackets: `[bill length mm] > 40`.
