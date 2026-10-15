# Row Filtering & Predicate Evaluation (`filter`)

`filter` extracts subset rows matching logical conditions, mathematical intervals, set memberships, string patterns, or Python callables. It maps cleanly between Python method chaining and CLI terminal piping.

---

## Rosetta Stone: Python vs. CLI

| Filter Type | Python Library (`pytae`) | Command Line (`pytae CLI`) |
|:---|:---|:---|
| **Simple Comparison** | `df.filter("body_mass_g > 4000")` | `-filter "body_mass_g > 4000"` |
| **Multiple Conditions (AND)** | `df.filter("body_mass_g > 4000 & species == 'Gentoo'")`<br>or `df.filter(body_mass_g="> 4000", species="Gentoo")` | `-filter "body_mass_g > 4000, species == 'Gentoo'"`<br>or `-filter "body_mass_g > 4000 & species == 'Gentoo'"` |
| **Logical OR** | `df.filter("species == 'Adelie' \| island == 'Dream'")` | `-filter "species == 'Adelie' \| island == 'Dream'"` |
| **Interval Range** | `df.filter(body_mass_g="[3000, 4500]")` | `-filter "body_mass_g = [3000, 4500]"` |
| **Set Membership** | `df.filter(species=["Adelie", "Gentoo"])`<br>or `df.filter("species in ['Adelie', 'Gentoo']")` | `-filter "species in ['Adelie', 'Gentoo']"` |
| **String Matching** | `df.filter("species.str.starts_with('Ade')")` | `-filter "species.str.starts_with('Ade')"` |
| **Columns with Spaces** | `df.filter("[bill length mm] > 40")` | `-filter "[bill length mm] > 40"` |
| **Null Checks** | `df.filter("sex.is_not_null()")` | `-filter "sex.is_not_null()"` |
| **Python Lambda / Callable** | `df.filter(lambda d: d['body_mass_g'] > 4000)` | *(Library only)* |

---

## Filter Syntax & Expressions

### 1. Mathematical Interval Ranges (`[]` and `()`)
Filter numeric columns within bounding ranges using clean mathematical bracket notation without typing repetitive `(col >= low) & (col <= high)`:
- `[low, high]`: Closed interval (`low <= col <= high`)
- `(low, high)`: Open interval (`low < col < high`)
- `[low, high)`: Half-open interval (`low <= col < high`)

```python
# In Python
penguins.filter(body_mass_g="[3500, 4200]")
penguins.filter(body_mass_g="(3000, 5000)")
```
```bash
# In CLI
pytae penguins.parquet -filter "body_mass_g = [3500, 4200]" -head 5
```

### 2. Set Membership (`in` and Python Lists)
Check if a column matches any element in a collection:

```python
# In Python: keyword list argument or string expression
penguins.filter(island=["Torgersen", "Dream"])
penguins.filter("species in ['Adelie', 'Chinstrap']")
```
```bash
# In CLI: SQL-like 'in' list or tuple
pytae penguins.parquet -filter "island in ['Torgersen', 'Dream']" -head 5
```

### 3. String Methods & Regex
Inspect string columns using standard vectorized string functions:

```python
# In Python
penguins.filter("species.str.starts_with('Gen')")
penguins.filter("island.str.contains('org')")
```
```bash
# In CLI
pytae penguins.parquet -filter "species.str.starts_with('Gen')" -head 3
```

### 4. Handling Columns with Spaces or Special Characters
Wrap column names containing spaces, dashes, or punctuation in square brackets `[column name]`:

```python
# In Python
df.filter("[bill length mm] > 40 & [total-cost] < 100")
```
```bash
# In CLI
pytae messy.parquet -filter "[bill length mm] > 40" -head 5
```

### 5. Python Lambdas & Custom Callables (Library Only)
For custom logic requiring complex Python functions or external libraries:

```python
def is_valid_weight(d):
    return (d["body_mass_g"] > 3500) & (d["sex"] == "Female")

penguins.filter(is_valid_weight)
penguins.filter(lambda d: d["flipper_length_mm"] % 2 == 0)
```

---

## Lazy Scanners: Predicate Pushdown

When filtering a lazy dataset (`pt.scan_parquet()` or `pt.scan_csv()`), `.filter()` operations are pushed down directly into the Parquet row group scanner. File chunks that do not satisfy the filter conditions are skipped without ever being read into RAM.
