# CLI Feature Guide: Distinct Rows (`-distinct`)

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
| `-distinct` | Bare flag | Drop duplicate rows checking all columns (`keep=first`) |
| `-distinct COLS` | Comma-separated list | Drop duplicate rows based on specified subset of columns |
| `-distinct "...keep=last"` | `keep=last` | Keep last occurrence instead of first |
| `-distinct "...keep=false"` | `keep=false` or `keep=none` | Drop all duplicate occurrences |

`-distinct` keeps unique combinations and resets the index to `0, 1, ...`. In the Python library, the equivalent is `pt.distinct(df, *cols, keep="first")` or `df.pt.distinct(*cols, keep="first")`.

---

## Deduplicating Across All Columns

Run `-distinct` as a bare flag to eliminate identical rows across the entire working dataset (equivalent to `df.pt.distinct()` or pandas `df.drop_duplicates()`):

```bash
# Keep only unique species and island pairs
pytae penguins.parquet -distinct "species,island"
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

## Controlling Which Duplicates to Keep (`keep=`)

Use `keep=` within the `-distinct` argument to control duplicate retention:

```bash
# Keep the last occurrence of each unique customer
pytae orders.parquet -distinct "customer_id,keep=last"

# Drop all duplicates (keep only rows that appeared exactly once)
pytae orders.parquet -distinct "customer_id,keep=false"

# Keep last duplicate across all columns
pytae events.parquet -distinct "keep=last"
```

---

## Deduplicating Across Specific Columns

Pass column names to restrict duplicate checks to specific identifiers, keeping the matching record for all other columns:

```bash
# Deduplicate based on customer identifier, retaining first order
pytae orders.parquet -distinct customer_id

# Deduplicate based on composite keys
pytae penguins.parquet -distinct "species,island"
```


---

## Chaining in Pipelines

`-distinct` operates seamlessly anywhere inside a multi-step pipeline:

```bash
# Filter rows -> select subset -> distinct -> sort -> output
pytae penguins.parquet \
  -filter "body_mass_g > 4000" \
  -select "species,island" \
  -distinct \
  -arrange species
```
