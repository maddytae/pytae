# Deduplication & Distinct Records (`distinct`)

`distinct` removes duplicate rows from a dataset. It operates across the entire row by default or restricts uniqueness to a designated subset of key columns, with full control over which occurrences to retain (`keep='first'|'last'|'none'`).

---

## Rosetta Stone: Python vs. CLI

| Capability | Python Library (`pytae`) | Command Line (`pytae CLI`) |
|:---|:---|:---|
| **Distinct All Columns** | `df.distinct()` | `-distinct` |
| **Distinct by Subset** | `df.distinct("species", "island")` | `-distinct "species, island"` |
| **Keep Last Occurrence** | `df.distinct("species", keep="last")` | `-distinct "species, keep=last"` |
| **Keep Unique Only** | `df.distinct("user_id", keep=False)` | `-distinct "user_id, keep=false"` |

---

## Python Library Usage

```python
import pytae as pt

penguins = pt.sample("penguins")

# Deduplicate all columns across the table
clean_df = penguins.distinct()

# Keep distinct combinations of species and island
unique_habitats = penguins.distinct("species", "island")

# Keep the last observed row per species
latest_per_species = penguins.distinct("species", keep="last")

# Keep only rows where user_id appears exactly once (drops all duplicated keys)
strict_singles = df.distinct("user_id", keep=False)
```

---

## CLI Usage

In the CLI, `-distinct` can be passed as a standalone flag or with arguments specifying key columns and retention strategy:

```bash
# Deduplicate entire file
pytae dirty.csv -distinct -o clean.parquet

# Unique combinations of columns
pytae penguins.parquet -distinct "species, island"

# Retain last occurrence
pytae transactions.parquet -distinct "customer_id, keep=last" -head 10
```
