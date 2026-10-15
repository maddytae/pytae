# 2D Cross-Tabulation & Contingency Tables (`pivot`)

`pivot` reshapes datasets into 2D summary matrices with rows along one axis, columns along another, and aggregated values in the cells. Unlike standard Pandas `pivot_table` which produces fragile hierarchical `MultiIndex` objects, Pytae always outputs clean, flat 1D columns ready for downstream chaining.

---

## Rosetta Stone: Python vs. CLI

| Parameter | Meaning | Python Library (`pytae`) | Command Line (`pytae CLI`) |
|:---|:---|:---|:---|
| `r=` | Row identifiers | `df.pivot(r="species", ...)` | `-pivot "r=species, ..."` |
| `c=` | Column categories | `df.pivot(..., c="island", ...)` | `-pivot "... c=island, ..."` |
| `v=` | Value column | `df.pivot(..., v="body_mass_g", ...)`| `-pivot "... v=body_mass_g, ..."` |
| `a=` | Aggregation function| `df.pivot(..., a="mean")` | `-pivot "... a=mean"` |
| `fill_value=`| Fill empty cells | `df.pivot(..., fill_value=0)` | `-pivot "... fill_value=0"` |
| `dropna=` | Keep NA keys | Default: `dropna=False` | Default: `dropna=False` |

---

## Python Library Usage

```python
import pytae as pt

penguins = pt.sample("penguins")

# 2D cross-tabulation: Mean body mass by species across islands
table = penguins.pivot(
    r="species",
    c="island",
    v="body_mass_g",
    a="mean"
)
```

**Output:**
```text
┌───────────┬─────────┬─────────┬───────────┐
│ species   ┆ Biscoe  ┆ Dream   ┆ Torgersen │
│ ---       ┆ ---     ┆ ---     ┆ ---       │
│ str       ┆ f64     ┆ f64     ┆ f64       │
╞═══════════╪═════════╪═════════╪═══════════╡
│ Adelie    ┆ 3709.66 ┆ 3688.39 ┆ 3706.37   │
│ Chinstrap ┆ null    ┆ 3733.09 ┆ null      │
│ Gentoo    ┆ 5076.02 ┆ null    ┆ null      │
└───────────┴─────────┴─────────┴───────────┘
```

### Filling Unobserved Combinations
Use `fill_value` to replace cells with zero counts or default values:

```python
penguins.pivot(
    r="species",
    c="island",
    v="body_mass_g",
    a="mean",
    fill_value=0
)
```

---

## CLI Usage

In the CLI, `-pivot` accepts the `r=`, `c=`, `v=`, and `a=` parameters inside a single quoted string:

```bash
# Basic cross-tabulation
pytae penguins.parquet -pivot "r=species, c=island, v=body_mass_g, a=mean"

# Count penguins by species across islands
pytae penguins.parquet -pivot "r=species, c=island, v=body_mass_g, a=count, fill_value=0"

# Filter before pivoting
pytae penguins.parquet \
  -filter "sex == 'Female'" \
  -pivot "r=species, c=island, v=flipper_length_mm, a=max"
```

