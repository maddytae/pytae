# CLI Feature Guide: Row Picking (`-pick`)

[← Back to CLI Reference Hub](../cli.md)

Extract top or bottom rows by column order, with group awareness via `-by`.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Top N Rows (`-pick`)](#top-n-rows--pick)
- [Bottom N Rows (`-pick ...,order=min`)](#bottom-n-rows--pick-ordermin)
- [Proportion Slicing (`prop=`)](#proportion-slicing-prop)
- [Group-Aware Picking (`-by`)](#group-aware-picking--by)
- [Specification Formats](#specification-formats)
- [Handling Ties & Missing Values](#handling-ties--missing-values)

---

## Overview & Quick Reference

| Flag | Description | Key Syntax |
|---|---|---|
| `-pick SPEC` | Select rows with largest (or smallest) values of a column | `-pick mass`, `-pick "mass,n=3"`, `-pick "mass,n=3,order=min"` |
| `-by COLS` | Partition rows into groups before picking | `-by species -pick "mass,n=2"` |

> [!NOTE]
> `-slice_max` and `-slice_min` are preserved as backward-compatible aliases pointing to `-pick`.

Both commands preserve all columns, reset the index to `0, 1, ...`, and preserve NA grouping categories.

---

## Top N Rows (`-pick`)

Extract the rows with the highest values of a target column. If `n` or `prop` is omitted, defaults to `n=1, order=max`:

```bash
# Top 3 heaviest penguins overall
pytae penguins.parquet -pick "body_mass_g,n=3" -select "species,island,body_mass_g"
```

**Output:**
```text
species island  body_mass_g
 Gentoo Biscoe       6300.0
 Gentoo Biscoe       6050.0
 Gentoo Biscoe       6000.0
```

---

## Bottom N Rows (`-pick ...,order=min`)

Extract the rows with the lowest values of a target column by specifying `order=min`:

```bash
# Lightest 3 penguins overall
pytae penguins.parquet -pick "body_mass_g,n=3,order=min" -select "species,island,body_mass_g"
```

**Output:**
```text
  species island  body_mass_g
Chinstrap  Dream       2700.0
   Adelie Biscoe       2850.0
   Adelie  Dream       2850.0
```

---

## Proportion Slicing (`prop=`)

Select a fraction of rows (e.g. `prop=0.1` for top 10%):

```bash
# Top 10% heaviest penguins overall
pytae penguins.parquet -pick "body_mass_g,prop=0.1" -select "species,island,body_mass_g"
```

---

## Group-Aware Picking (`-by`)

When combined with `-by`, `pick` extracts top or bottom rows **within each unique group**:

```bash
# Heaviest penguin for each species (default n=1, order=max)
pytae penguins.parquet -by species -pick body_mass_g -select "species,island,body_mass_g"
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
pytae penguins.parquet -by island -pick "body_mass_g,n=2,order=min" -select "island,species,body_mass_g"

# Top 20% heaviest penguins within each species
pytae penguins.parquet -by species -pick "body_mass_g,prop=0.2" -select "species,island,body_mass_g"
```

---

## Specification Formats

The canonical, unified syntax:
- **Exact row count (`n=N`)**: `-pick "body_mass_g,n=3"`
- **Bottom rows (`order=min`)**: `-pick "body_mass_g,n=3,order=min"`
- **Proportion of rows (`prop=P`)**: `-pick "body_mass_g,prop=0.1"`
- **Default `n=1, order=max`**: `-pick body_mass_g`
- **Columns with spaces**: wrap in brackets, e.g. `-pick "[bill length mm],n=3"`

---

## Handling Ties & Missing Values

- By default, picking does not include ties beyond `n` (`with_ties=False`).
- Missing values (`NaN`) in the ranking column appear at the bottom by default (`na_last=True`).
- Missing values in grouping columns (`-by`) form their own group without silent row loss. To omit missing groups, chain `-dropna` before picking:

```bash
pytae penguins.parquet -dropna sex -by sex -pick body_mass_g
```
