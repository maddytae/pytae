# CLI Feature Guide: Row Sorting (`-arrange`)

[← Back to CLI Reference Hub](../cli.md)

Order DataFrame rows by one or more columns with full support for descending orders (`desc`) and bracket notation for columns with spaces.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Ascending Sort (Default)](#ascending-sort-default)
- [Descending Sort (`desc`)](#descending-sort-desc)
- [Multi-Column Sorting](#multi-column-sorting)
- [Columns With Spaces (`[col name]`)](#columns-with-spaces-col-name)

---

## Overview & Quick Reference

| Flag | Syntax / Format | Description |
|---|---|---|
| `-arrange SPEC` | `col` | Sort ascending (default) |
| `-arrange SPEC` | `col desc` | Sort descending |
| `-arrange SPEC` | `col1, col2 desc` | Multi-column hierarchical sort |
| `-arrange SPEC` | `"[col name] desc"` | Sort columns containing spaces |

---

## Ascending Sort (Default)

By default, `-arrange` sorts rows in ascending order:

```bash
# Sort ascending by body mass
pytae penguins.parquet -arrange body_mass_g -select "species,island,body_mass_g" -head 5
```

**Output:**

| species | island | body_mass_g |
|:---|:---|---:|
| Chinstrap | Dream | 2700.0 |
| Adelie | Biscoe | 2850.0 |
| Adelie | Biscoe | 2850.0 |
| Adelie | Torgersen | 2900.0 |
| Adelie | Dream | 2900.0 |

---

## Descending Sort (`desc`)

In line with *"one and only one obvious way"*, specify descending order explicitly by appending `desc` or `descending` to the column name:

```bash
# Explicit 'desc'
pytae penguins.parquet -arrange "body_mass_g desc" -select "species,island,body_mass_g" -head 5
```

**Output:**

| species | island | body_mass_g |
|:---|:---|---:|
| Gentoo | Biscoe | 6300.0 |
| Gentoo | Biscoe | 6050.0 |
| Gentoo | Biscoe | 6000.0 |
| Gentoo | Biscoe | 6000.0 |
| Gentoo | Biscoe | 5950.0 |

---

## Multi-Column Sorting

Pass multiple columns separated by commas:

```bash
# Species ascending, body mass descending
pytae penguins.parquet -arrange "species, body_mass_g desc" -select "species,island,body_mass_g" -head 6
```

**Output:**

| species | island | body_mass_g |
|:---|:---|---:|
| Adelie | Biscoe | 4775.0 |
| Adelie | Biscoe | 4725.0 |
| Adelie | Torgersen | 4700.0 |
| Adelie | Torgersen | 4675.0 |
| Adelie | Dream | 4650.0 |
| Adelie | Dream | 4600.0 |

---

## Columns With Spaces (`[col name]`)

Columns with spaces are cleanly referenced using square brackets:

```bash
pytae sales.csv -arrange "[annual revenue] desc" -head 5
```

**Output:**

| annual revenue | region |
|---:|:---|
| 450000 | Central |
| 310000 | East |
| 180000 | Pacific |
| 120000 | North |
| 95000 | West |
