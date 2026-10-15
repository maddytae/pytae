# Row Sorting & Ordering (`arrange`)

`arrange` orders rows by one or more columns in ascending or descending order. It provides an intuitive shorthand syntax (`-col` or `col desc`) avoiding clumsy boolean arrays or multiple sort arguments.

---

## Rosetta Stone: Python vs. CLI

| Sort Order | Python Library (`pytae`) | Command Line (`pytae CLI`) |
|:---|:---|:---|
| **Ascending** | `df.arrange("body_mass_g")` | `-arrange body_mass_g` |
| **Descending (Dash)** | `df.arrange("-body_mass_g")` | `-arrange "-body_mass_g"` |
| **Descending (Keyword)**| `df.arrange("body_mass_g desc")` | `-arrange "body_mass_g desc"` |
| **Multi-Column Sort** | `df.arrange("species", "-body_mass_g")` | `-arrange "species, -body_mass_g"` |
| **Columns with Spaces** | `df.arrange("-[bill length mm]")` | `-arrange "-[bill length mm]"` |

---

## Python Library Usage

```python
import pytae as pt

penguins = pt.sample("penguins")

# Sort ascending by body mass
df_asc = penguins.arrange("body_mass_g")

# Sort descending using leading dash
df_desc = penguins.arrange("-body_mass_g")

# Multi-column sort: Species ascending, then body mass descending
df_multi = penguins.arrange("species", "-body_mass_g")

# Columns with spaces
df_space = penguins.arrange("-[bill length mm]")
```

---

## CLI Usage

In the CLI, `-arrange` accepts column names separated by commas. Use quotes if passing negative signs `-col` or `desc`:

```bash
# Ascending sort
pytae penguins.parquet -arrange body_mass_g -head 5

# Descending sort (dash notation)
pytae penguins.parquet -arrange "-body_mass_g" -head 5

# Descending sort (desc keyword)
pytae penguins.parquet -arrange "body_mass_g desc" -head 5

# Multi-column sort
pytae penguins.parquet -arrange "species, -body_mass_g" -head 10
```

> [!TIP]
> In bash/zsh, always quote negative column names (`"-col"`) so the shell does not mistake the leading dash for a CLI flag.
