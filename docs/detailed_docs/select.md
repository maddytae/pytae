# Column Selection & Reordering (`select`)

`select` subsets, excludes, reorders, and renames columns. It supports explicit column names, negative exclusion flags (`-` or `!`), pattern matching, bracketed identifiers with spaces, and projection pushdown across both Python and CLI.

---

## Rosetta Stone: Python vs. CLI

| Capability | Python Library (`pytae`) | Command Line (`pytae CLI`) |
|:---|:---|:---|
| **Select Columns** | `df.select("species", "body_mass_g")` | `-select "species, body_mass_g"` |
| **Drop / Exclude Columns**| `df.select("-species", "-island")`<br>or `df.select("!species", "!island")` | `-select "-species, -island"`<br>or `-select "!species, !island"` |
| **Rename in Select** | `df.select(mass="body_mass_g", "species")`<br>or `df.select("mass = body_mass_g, species")` | `-select "mass = body_mass_g, species"` |
| **Pattern: Starts With** | `df.select(startswith="bill_")` | `-select "startswith=bill_"` |
| **Pattern: Ends With** | `df.select(endswith="_mm")` | `-select "endswith=_mm"` |
| **Pattern: Contains** | `df.select(contains="length")` | `-select "contains=length"` |
| **Pattern: Regex** | `df.select(regex=r"^(bill\|flipper)")` | `-select "regex=^(bill\|flipper)"` |
| **Reorder with Rest** | `df.select("body_mass_g", pt.everything)` | *(CLI: use explicit order)* |
| **Columns with Spaces** | `df.select("[bill length mm]", "island")` | `-select "[bill length mm], island"` |

---

## Python Library Usage

### 1. Inclusion & Exclusion
Pass column names as positional arguments. Prefix column names with `-` or `!` to drop them:

```python
import pytae as pt

penguins = pt.sample("penguins")

# Keep specific columns
penguins.select("species", "island", "body_mass_g")

# Drop specific columns
penguins.select("-sex", "-island")
penguins.select("!bill_length_mm", "!bill_depth_mm")
```

### 2. Renaming in Select
Rename columns on-the-fly without needing a separate `.rename()` call:

```python
penguins.select(species="species", weight_g="body_mass_g", location="island")
```

### 3. Reordering Columns with `pt.everything`
Move critical metric columns to the front of the DataFrame while preserving all other columns in their original order:

```python
# Move body_mass_g to the first column
penguins.select("body_mass_g", pt.everything)
```

### 4. Pattern Selectors
Match columns dynamically using pattern keywords:

```python
# All bill measurements
penguins.select(startswith="bill_")

# All millimeter metrics
penguins.select(endswith="_mm")

# Any column containing 'mass'
penguins.select(contains="mass")
```

---

## CLI Usage

In the CLI, `-select` accepts a comma-separated list of column names, exclusion flags, or pattern matchers:

```bash
# Keep specific columns
pytae penguins.parquet -select "species, island, body_mass_g" -head 5

# Exclude columns (leading dash or exclamation point)
pytae penguins.parquet -select "-sex, -island" -head 5

# Inline renaming
pytae penguins.parquet -select "weight = body_mass_g, species" -head 5

# Pattern selection
pytae penguins.parquet -select "startswith=bill_" -head 3
pytae penguins.parquet -select "contains=length" -head 3

# Selecting columns with spaces
pytae sales.parquet -select "[Customer Name], [Total Spend]" -head 5
```

---

## Lazy Scanners: Projection Pushdown

When reading large Parquet or CSV datasets using `pt.scan_parquet()` or `pt.scan_csv()`, calling `.select()` informs the Polars query optimizer to only load the selected columns from disk, completely skipping unselected columns and saving significant I/O bandwidth.

