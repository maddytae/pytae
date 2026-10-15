# Slicing Top & Bottom Records (`pick`)

`pick` extracts the top or bottom $N$ records (or proportion) ordered by a metric column. When preceded by `.by()`, it slices top/bottom records **per group**, eliminating verbose window rank filters.

---

## Rosetta Stone: Python vs. CLI

| Capability | Python Library (`pytae`) | Command Line (`pytae CLI`) |
|:---|:---|:---|
| **Top N Overall** | `df.pick("body_mass_g", n=5)` | `-pick "body_mass_g, n=5"` |
| **Bottom N Overall** | `df.pick("body_mass_g", n=5, order="min")` | `-pick "body_mass_g, n=5, order=min"` |
| **Top Percentage / Proportion**| `df.pick("body_mass_g", prop=0.05)` | `-pick "body_mass_g, prop=0.05"` |
| **Top N Per Group** | `df.by("species").pick("body_mass_g", n=2)` | `-by species -pick "body_mass_g, n=2"` |
| **Bottom N Per Group** | `df.by("species").pick("body_mass_g", n=2, order="min")` | `-by species -pick "body_mass_g, n=2, order=min"` |

---

## Python Library Usage

```python
import pytae as pt

penguins = pt.sample("penguins")

# Top 5 heaviest penguins across entire dataset
top5 = penguins.pick("body_mass_g", n=5)

# Bottom 3 lightest penguins
lightest3 = penguins.pick("body_mass_g", n=3, order="min")

# Top 10% highest flipper lengths
top_10_pct = penguins.pick("flipper_length_mm", prop=0.10)

# Top 2 heaviest penguins PER species
top_per_species = penguins.by("species").pick("body_mass_g", n=2)
```

---

## CLI Usage

In the CLI, `-pick` accepts the metric column, `n=` or `prop=`, and optional `order=max|min`:

```bash
# Top 5 heaviest overall
pytae penguins.parquet -pick "body_mass_g, n=5"

# Bottom 5 lightest overall
pytae penguins.parquet -pick "body_mass_g, n=5, order=min"

# Top 2 per species
pytae penguins.parquet -by species -pick "body_mass_g, n=2"
```

