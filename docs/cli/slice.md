# CLI Feature Guide: Row Slicing (`-slice_max`, `-slice_min`)

[← Back to CLI Reference Hub](../cli.md)

Extract top or bottom rows by column order, with group awareness via `-by`.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Top N Rows (`-slice_max`)](#top-n-rows--slice_max)
- [Bottom N Rows (`-slice_min`)](#bottom-n-rows--slice_min)
- [Group-Aware Slicing (`-by`)](#group-aware-slicing--by)
- [Specification Formats (`col:N`, `col,n=N`)](#specification-formats)
- [Handling Ties & Missing Values](#handling-ties--missing-values)

---

## Overview & Quick Reference

| Flag | Description | Key Syntax |
|---|---|---|
| `-slice_max SPEC` | Select rows with largest values of a column | `-slice_max mass`, `-slice_max "mass:3"`, `-slice_max "mass,n=3"` |
| `-slice_min SPEC` | Select rows with smallest values of a column | `-slice_min mass`, `-slice_min "mass:3"`, `-slice_min "mass,n=3"` |
| `-by COLS` | Partition rows into groups before slicing | `-by species -slice_max "mass:2"` |

Both commands preserve all columns, reset the index to `0, 1, ...`, and preserve NA grouping categories.

---

## Top N Rows (`-slice_max`)

Extract the rows with the highest values of a target column. If `N` is omitted, defaults to `n=1`:

```bash
# Top 3 heaviest penguins overall
pytae penguins.parquet -slice_max "body_mass_g:3" -select "species,island,body_mass_g"
```

**Output:**
```text
species island  body_mass_g
 Gentoo Biscoe       6300.0
 Gentoo Biscoe       6050.0
 Gentoo Biscoe       6000.0
```

---

## Bottom N Rows (`-slice_min`)

Extract the rows with the lowest values of a target column:

```bash
# Lightest 3 penguins overall
pytae penguins.parquet -slice_min "body_mass_g:3" -select "species,island,body_mass_g"
```

**Output:**
```text
  species island  body_mass_g
Chinstrap  Dream       2700.0
   Adelie Biscoe       2850.0
   Adelie  Dream       2850.0
```

---

## Group-Aware Slicing (`-by`)

When combined with `-by`, `slice_max` and `slice_min` extract top or bottom N rows **within each unique group**:

```bash
# Heaviest penguin for each species
pytae penguins.parquet -by species -slice_max "body_mass_g:1" -select "species,island,body_mass_g"
```

**Output:**
```text
  species island  body_mass_g
   Adelie Biscoe       4775.0
Chinstrap  Dream       4800.0
   Gentoo Biscoe       6300.0
```

```bash
# Lightest 2 penguins per island
pytae penguins.parquet -by island -slice_min "body_mass_g:2" -select "island,species,body_mass_g"
```

---

## Specification Formats

Flexible ways to specify the ranking column and row count:
- Colon format: `-slice_max "body_mass_g:3"`
- Comma format: `-slice_max "body_mass_g,3"`
- Keyword format: `-slice_max "body_mass_g,n=3"`
- Default `n=1`: `-slice_max body_mass_g`
- Columns with spaces: wrap in brackets, e.g. `-slice_max "[bill length mm]:3"`

---

## Handling Ties & Missing Values

- By default, rank slicing does not include ties beyond `n` (`with_ties=False`).
- Missing values (`NaN`) in the ranking column appear at the bottom by default (`na_last=True`).
- Missing values in grouping columns (`-by`) form their own group without silent row loss. To omit missing groups, chain `-dropna` before slicing:

```bash
pytae penguins.parquet -dropna sex -by sex -slice_max "body_mass_g:1"
```
