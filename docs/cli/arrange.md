# CLI Feature Guide: Row Sorting (`-arrange`)

[← Back to CLI Reference Hub](../cli.md)

Order DataFrame rows by one or more columns with full support for descending orders (`desc`, `-col`) and bracket notation for columns with spaces.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Ascending Sort (Default)](#ascending-sort-default)
- [Descending Sort (`desc`, `-col`)](#descending-sort-desc--col)
- [Multi-Column Sorting](#multi-column-sorting)
- [Columns With Spaces (`[col name]`)](#columns-with-spaces-col-name)

---

## Overview & Quick Reference

| Flag | Syntax / Format | Description |
|---|---|---|
| `-arrange SPEC` | `col` | Sort ascending (default) |
| `-arrange SPEC` | `col desc` or `-col` | Sort descending |
| `-arrange SPEC` | `col1, col2 desc` | Multi-column hierarchical sort |
| `-arrange SPEC` | `"[col name] desc"` | Sort columns containing spaces |

---

## Ascending Sort (Default)

By default, `-arrange` sorts rows in ascending order:

```bash
# Sort ascending by body mass
pytae penguins.parquet -arrange body_mass_g -select "species,island,body_mass_g" -head 5
```

---

## Descending Sort (`desc`, `-col`)

Specify descending order using trailing `desc` / `descending`, or leading `-`:

```bash
# Explicit 'desc'
pytae penguins.parquet -arrange "body_mass_g desc" -select "species,island,body_mass_g" -head 5

# Leading minus shorthand
pytae penguins.parquet -arrange "-body_mass_g" -select "species,island,body_mass_g" -head 5
```

---

## Multi-Column Sorting

Pass multiple columns separated by commas:

```bash
# Species ascending, body mass descending
pytae penguins.parquet -arrange "species, body_mass_g desc" -select "species,island,body_mass_g" -head 6

# Shorthand notation
pytae penguins.parquet -arrange "species, -body_mass_g" -select "species,island,body_mass_g" -head 6
```

---

## Columns With Spaces (`[col name]`)

Columns with spaces are cleanly referenced using square brackets:

```bash
pytae sales.csv -arrange "[annual revenue] desc" -head 5
```
