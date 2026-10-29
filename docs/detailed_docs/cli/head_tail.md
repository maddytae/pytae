# CLI Feature Guide: Row Slicing (`-head` & `-tail`)

[← Back to Master Reference](../../pytae.md)

Extract first, last, or extreme rows with full group awareness via `-by`, proportion limits (`10%`), and boundary tie handling (`ties=true`).

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Basic Slicing](#basic-slicing)
- [Proportion Slicing (`10%` / `0.1`)](#proportion-slicing-10--01)
- [Extreme Value Slicing](#extreme-value-slicing)
- [Group-Aware Slicing (`-by`)](#group-aware-slicing--by)
- [Boundary Ties (`ties=true`)](#boundary-ties-tiestrue)
- [Retirement of Legacy `-pick`](#retirement-of-legacy--pick)

---

## Overview & Quick Reference

| Flag | Description | Examples |
|---|---|---|
| `-head [LIMIT]` | Extract first $N$ rows, percentage, or proportion | `-head 5`, `-head 10%`, `-head 0.1`, `-head "3, ties=true"` |
| `-tail [LIMIT]` | Extract last $N$ rows, percentage, or proportion | `-tail 5`, `-tail 10%`, `-tail 0.1`, `-tail "3, ties=true"` |
| `-by COLS` | Partition rows into groups before slicing | `-by species -head 2`, `-by species -arrange "mass desc" -head 1` |

When `-head` or `-tail` is passed without an explicit limit, it defaults to 5 rows. Slicing preserves column order, resets the row index, and cleanly ungroups.

---

## Basic Slicing

Extract the first or last $N$ rows of the table:

```bash
# First 3 rows
pytae penguins.parquet -head 3 -select "species,island,body_mass_g"
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Adelie    | Torgersen|          3750 |
| Adelie    | Torgersen|          3800 |
| Adelie    | Torgersen|          3250 |

```bash
# Last 3 rows
pytae penguins.parquet -tail 3 -select "species,island,body_mass_g"
```

---

## Proportion Slicing (`10%` / `0.1`)

Slice a percentage or fraction of rows by passing `%` or a float:

```bash
# First 5% of rows
pytae penguins.parquet -head 5% -shape
```

**Output:**
```
(17, 7)
```

Both percentages (`-head 10%`) and floating-point fractions (`-head 0.1`) are accepted.

---

## Extreme Value Slicing

In accordance with Pytae's *"One and Only One Obvious Way"*, extreme row selection (top/bottom $N$ by column) is achieved by composing `-arrange` with `-head` or `-tail`:

### Top N Rows Overall

```bash
# Top 3 heaviest penguins overall
pytae penguins.parquet -arrange "body_mass_g desc" -head 3 -select "species,island,body_mass_g"
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Gentoo    | Biscoe   |          6300 |
| Gentoo    | Biscoe   |          6050 |
| Gentoo    | Biscoe   |          6000 |

### Bottom N Rows Overall

```bash
# Lightest 3 penguins overall
pytae penguins.parquet -arrange body_mass_g -head 3 -select "species,island,body_mass_g"
```

*(Alternatively: `pytae penguins.parquet -arrange "body_mass_g desc" -tail 3`)*

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Chinstrap | Dream    |          2700 |
| Adelie    | Biscoe   |          2850 |
| Adelie    | Dream    |          2850 |

---

## Group-Aware Slicing (`-by`)

When combined with `-by`, `-head` and `-tail` extract rows **within each unique group**:

### Heaviest Penguin per Species

```bash
# Top 1 heaviest penguin for each species
pytae penguins.parquet -by species -arrange "body_mass_g desc" -head 1 -select "species,island,body_mass_g"
```

**Output:**

| species   | island   |   body_mass_g |
|:----------|:---------|--------------:|
| Adelie    | Biscoe   |          4775 |
| Chinstrap | Dream    |          4800 |
| Gentoo    | Biscoe   |          6300 |

### Lightest 2 Penguins per Island

```bash
pytae penguins.parquet -by island -arrange body_mass_g -head 2 -select "island,species,body_mass_g"
```

**Output:**

| island    | species   |   body_mass_g |
|:----------|:----------|--------------:|
| Biscoe    | Adelie    |          2850 |
| Biscoe    | Adelie    |          2850 |
| Dream     | Chinstrap |          2700 |
| Dream     | Adelie    |          2900 |
| Torgersen | Adelie    |          2900 |
| Torgersen | Adelie    |          3050 |

### Top 10% per Group

```bash
pytae penguins.parquet -by species -arrange "body_mass_g desc" -head 10% -select "species,island,body_mass_g"
```

### Top N per Group in Chained Pipelines (Sequential `-by`)

In Pytae CLI, `-by` operates with **single-shot zero-pollution scoping**: each `-by` applies strictly to the verb that follows, then resets. You can seamlessly chain aggregation, sorting, and group-aware slicing in a single command:

```bash
# Top 2 species by average body mass for each island
pytae penguins.parquet \
  -by island,species -agg "avg_mass=mean(body_mass_g)" \
  -arrange "island, avg_mass desc" \
  -by island -head 2
```

**Output:**

| island    | species   |   avg_mass |
|:----------|:----------|-----------:|
| Biscoe    | Gentoo    |    5076.02 |
| Biscoe    | Adelie    |    3709.66 |
| Dream     | Chinstrap |    3733.09 |
| Dream     | Adelie    |    3688.39 |
| Torgersen | Adelie    |    3706.37 |

---

## Boundary Ties (`ties=true`)

When multiple rows share the exact value at the $N$-th boundary rank, pass `ties=true` to include all tied rows:

```bash
# Include ties at the rank boundary
pytae penguins.parquet -arrange "body_mass_g desc" -head "3, ties=true" -select "species,island,body_mass_g"
```

---

## Retirement of Legacy `-pick`

The niche verb `-pick` has been removed. In Pytae:
- Selecting top records is simply `-arrange "col desc" -head N`.
- Selecting bottom records is `-arrange col -head N` (or `-arrange "col desc" -tail N`).
- Grouped extreme selection is `-by group -arrange "col desc" -head N`.

Calling `-pick` raises an immediate, helpful redirect error guiding users to compose `-arrange` and `-head`/`-tail`.
