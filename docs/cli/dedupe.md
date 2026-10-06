# CLI Feature Guide: Deduplication (`-dedupe`)

[← Back to CLI Reference Hub](../cli.md)

Drop duplicate rows across the intermediate DataFrame with full control over column subsets.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Deduplicating Across All Columns](#deduplicating-across-all-columns)
- [Deduplicating Across Specific Columns](#deduplicating-across-specific-columns)
- [Chaining in Pipelines](#chaining-in-pipelines)

---

## Overview & Quick Reference

| Flag | Syntax / Format | Description |
|---|---|---|
| `-dedupe` | Bare flag | Drop duplicate rows checking all columns |
| `-dedupe COLS` | Comma-separated list | Drop duplicate rows based on specified subset of columns |

`-dedupe` keeps the first occurrence of each unique combination and resets the index to `0, 1, ...`. In the Python library, the equivalent is `pt.dedupe(df, *cols)` or `df.pt.dedupe(*cols)`.

---

## Deduplicating Across All Columns

Run `-dedupe` as a bare flag to eliminate identical rows across the entire working dataset (equivalent to `df.pt.dedupe()` or pandas `df.drop_duplicates()`):

```bash
# Keep only unique species and island pairs
pytae penguins.parquet -select "species,island" -dedupe
```

**Output:**
```text
  species    island
   Adelie Torgersen
   Adelie    Biscoe
   Adelie     Dream
Chinstrap     Dream
   Gentoo    Biscoe
```

---

## Deduplicating Across Specific Columns

Pass column names to restrict duplicate checks to specific identifiers, keeping the first matching record for all other columns:

```bash
# Deduplicate based on customer identifier, retaining first order
pytae orders.parquet -dedupe customer_id

# Deduplicate based on composite keys
pytae penguins.parquet -dedupe "species,island"
```

---

## Chaining in Pipelines

`-dedupe` operates seamlessly anywhere inside a multi-step pipeline:

```bash
# Filter rows -> select subset -> deduplicate -> sort -> output
pytae penguins.parquet \
  -qry "body_mass_g > 4000" \
  -select "species,island" \
  -dedupe \
  -arrange species
```
