# CLI Feature Guide: Row Filtering & Slicing

[← Back to CLI Reference Hub](../cli.md)

Filter rows using pytae's ergonomic filter expressions (`-filter`), drop missing rows (`-dropna`), or extract extreme rows (`-slice_max`, `-slice_min`).

---

## Contents

- [Overview & Differences](#overview--differences)
- [Pytae Filtering (`-filter`)](#pytae-filtering--filter)
  - [Exact Matching](#exact-matching)
  - [Comparisons (`>`, `<`, `>=`, `<=`, `!=`)](#comparisons)
  - [Intervals & Ranges (`[start, end]`)](#intervals--ranges)
  - [List Membership (`['a', 'b']`)](#list-membership)
  - [Combining Multiple Conditions](#combining-multiple-conditions)
- [Selecting Extreme Rows (`-slice_max`, `-slice_min`)](#selecting-extreme-rows--slice_max--slice_min)
- [Dropping Missing Values (`-dropna`)](#dropping-missing-values--dropna)
- [Quoting Best Practices](#quoting-best-practices)

---

## Overview & Differences

| Flag | Category | Key Syntax Highlights |
|---|---|---|
| `-filter CONDITIONS` | Row Filter | Comma-separated conditions, intervals `col = [min, max]`, list membership `col = ['a', 'b']`, bracketed spaces `[col name]` |
| `-dropna [COLS]` | Row Filter | Drops rows containing `NaN` (bare for all columns, or comma-separated subset) |
| `-slice_max SPEC` | Row Slicing | Select top N rows by column (`col:N`, `col,N`, or `col,n=N`), group-aware with `-by` |
| `-slice_min SPEC` | Row Slicing | Select bottom N rows by column (`col:N`, `col,N`, or `col,n=N`), group-aware with `-by` |

> [!NOTE]
> `-qry` is preserved as a backward-compatible alias pointing to `-filter`.

---

## Pytae Filtering (`-filter`)

Pytae's `-filter` simplifies row filtering with clean, human-readable syntax.

### Exact Matching

String values inside `-filter` must be enclosed in single quotes `'value'`:

```bash
pytae penguins.parquet -filter "species = 'Gentoo'" -head 3
```

**Output:**
```text
species island  bill_length_mm  bill_depth_mm  flipper_length_mm  body_mass_g    sex
 Gentoo Biscoe            46.1           13.2              211.0       4500.0 Female
 Gentoo Biscoe            50.0           16.3              230.0       5700.0   Male
 Gentoo Biscoe            48.7           14.1              210.0       4450.0 Female
```

<a id="comparisons"></a>
### Comparisons (`>`, `<`, `>=`, `<=`, `!=`)

```bash
pytae penguins.parquet -filter "body_mass_g > 5500" -select "species,island,body_mass_g" -head 3
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
pytae penguins.parquet -filter "body_mass_g = [3000, 3200]" -select "species,body_mass_g" -head 3
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
pytae penguins.parquet -filter "species = ['Chinstrap', 'Gentoo']" -select "species,island" -head 3
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
  -filter "species = 'Gentoo', body_mass_g > 5500, island = 'Biscoe'" \
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

## Selecting Extreme Rows (`-slice_max`, `-slice_min`)

Extract the top or bottom N rows ordered by a specific column. Both verbs are fully group-aware when combined with `-by`.

Supported specification formats:
- Exact count: `col,n=N` (e.g. `body_mass_g,n=3`)
- Proportion: `col,prop=P` (e.g. `body_mass_g,prop=0.1`)
- Default `n=1` if `n` and `prop` are omitted (e.g. `body_mass_g`)
- Bracketed notation `[col with spaces],n=N` is supported.

### Top N Rows Overall

```bash
pytae penguins.parquet -slice_max "body_mass_g,n=3" -select "species,island,body_mass_g"
```

**Output:**
```text
species island  body_mass_g
 Gentoo Biscoe       6300.0
 Gentoo Biscoe       6050.0
 Gentoo Biscoe       6000.0
```

### Bottom N Rows per Group (`-by`)

When combined with `-by`, `slice_min` extracts the smallest N rows within each unique group:

```bash
pytae penguins.parquet -by species -slice_min "body_mass_g:1" -select "species,body_mass_g"
```

**Output:**
```text
  species  body_mass_g
   Adelie       2850.0
Chinstrap       2700.0
   Gentoo       3950.0
```

---

## Dropping Missing Values (`-dropna`)

Drop rows with missing values (`NaN`). Can be run bare or scoped to a comma-separated column list:

```bash
# Drop rows with NaN in any column
pytae penguins.parquet -dropna

# Drop rows with NaN in specific column(s)
pytae penguins.parquet -dropna "body_mass_g,sex"
```

> [!NOTE]
> For scoped aggregations and pivot tables, pass `dropna=true` inside the operation's spec (e.g., `-agg "a=mean,dropna=true"` or `-pivot "r=species,c=sex,dropna=true"`).

---

## Quoting Best Practices

In terminal shells (bash, zsh):
- Enclose the entire spec in outer double quotes: `-filter "..."`.
- Enclose string literals in inner single quotes: `'Gentoo'`.
- Columns with spaces should be wrapped in brackets: `[bill length mm] > 40` or `-slice_max "[bill length mm]:3"`.
