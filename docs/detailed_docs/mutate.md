# Feature Engineering & Column Derivations (`mutate`)

`mutate` creates, derives, and transforms columns in-place while strictly preserving the number of rows ($N \to N$). It powers feature engineering, mathematical scaling, window functions, conditional branching, string formatting, and missing value imputation across both the Python library and CLI.

---

## Rosetta Stone: Python vs. CLI

| Operation | Python Library (`pytae`) | Command Line (`pytae CLI`) |
|:---|:---|:---|
| **Simple Math** | `df.mutate(ratio="bill_length_mm / bill_depth_mm")` | `-mutate "ratio = bill_length_mm / bill_depth_mm"` |
| **String Assignment** | `df.mutate(status="'active'")` | `-mutate "status = 'active'"` |
| **Numeric Scalar** | `df.mutate(multiplier=1.5)` | `-mutate "multiplier = 1.5"` |
| **Sequential Derivations** | `df.mutate(a="1", b="a * 2")` | `-mutate "a = 1, b = a * 2"` |
| **Conditional (`if_else`)** | `df.mutate(flag="if_else(x > 0, 'pos', 'neg')")` | `-mutate "flag = if_else(x > 0, 'pos', 'neg')"` |
| **Multi-Branch (`case_when`)**| `df.mutate(t="case_when((x > 10, 'hi'), (x > 0, 'lo'), 'neg')")` | `-mutate "t = case_when((x > 10, 'hi'), (x > 0, 'lo'), 'neg')"` |
| **String & Null Checks** | `df.mutate(ok="id.str.contains('-A') \| tag.is_not_null()")` | `-mutate "ok = id.str.contains('-A') \| tag.is_not_null()"` |
| **Multi-Column (`across`)**| `df.mutate("(a, b) = _ * 1.08")` | `-mutate "(a, b) = _ * 1.08"` |
| **Multi-Column + Suffix** | `df.mutate("(a, b)_usd = _ * 1.08")` | `-mutate "(a, b)_usd = _ * 1.08"` |
| **Smart `fillna`** | `df.mutate(clean="fillna(x, 0, nans=True)")` | `-mutate "clean = fillna(x, 0, nans=True)"` |
| **Grouped Window Calculation**| `df.by("species").mutate(m="mean(body_mass_g)")`| `-by species -mutate "m = mean(body_mass_g)"` |
| **Custom Python Function** | `df.mutate(out="my_func(col1, col2)")` | *(Library only)* |

---

## Core Principles & Semantics

1. **Strict Table Shape Preservation**:
   - `mutate` never drops rows. Any row filtering or row deduplication must be done using `filter` or `distinct`.
2. **Left-to-Right Sequential Resolution & Interleaved Callables**:
   - New columns defined on the left are immediately available for downstream calculations on the right within the same `mutate` call:
   ```python
   # 'total' can immediately be used in 'tax'
   df.mutate(total="price * qty", tax="total * 0.08")
   ```
   - Python callables (functions or lambdas) and string expressions can be freely interleaved in insertion order. Downstream expressions can seamlessly reference columns created by upstream callables:
   ```python
   # 'b' uses callable result 'a', and 'c' uses 'b'
   df.mutate(
       a=lambda d: d["x"] * 2,
       b="a + 10",
       c=lambda d: d["b"] * 3
   )
   ```
3. **Literal Values**:
   - Native Python types (`int`, `float`, `bool`) are converted directly to constant columns: `count=10, flag=True`.
   - String literals must be wrapped in inner quotes to distinguish them from column names: `status="'active'"` or `"status = 'active'"`. Bare strings like `status="col_name"` copy or alias the existing column `col_name`.

---

## Python Library Usage

### 1. Basic Transformations & Keyword Syntax

```python
import pytae as pt

penguins = pt.sample("penguins")

# Using keyword arguments
df1 = penguins.mutate(
    body_mass_kg="body_mass_g / 1000",
    status="'active'",
    verified=True
)

# Using single formula string
df2 = penguins.mutate("body_mass_kg = body_mass_g / 1000, status = 'active'")
```

### 2. Multi-Column Transformations (`across` Syntax)

Transform multiple columns at once using the concise tuple shorthand `(col1, col2, ...) = _ * expression`:

```python
# Transform in place (replaces original columns)
penguins.mutate("(bill_length_mm, bill_depth_mm) = _ / 10")

# Transform and append with suffix
penguins.mutate("(bill_length_mm, bill_depth_mm)_cm = _ / 10")
```

### 3. Conditional Expressions (`if_else` / `case_when`)

```python
# Binary condition
penguins.mutate(
    size_category="if_else(body_mass_g > 4000, 'Large', 'Normal')"
)

# Multi-condition with case_when (tuple pairs + default)
penguins.mutate(
    tier="""
    case_when(
        (body_mass_g > 5000, 'Heavy'),
        (body_mass_g > 3500, 'Medium'),
        'Light'
    )
    """
)

# Complex domain branching with string matching, bitwise OR (|), and null checks
deals.mutate(
    tranche_type="""
    case_when(
        (deal_identifier == tranche_id, 'Main Tranche'),
        (tranche_id.str.contains('-COL-') | collateral_class.is_not_null(), 'Collateral'),
        'Guarantor'
    )
    """
)
```

### 4. Smart Missing Imputation Inside `mutate`

Pytae provides smart missing value helpers inside `mutate`:
- `fillna(col, value, nans=True)`: Replaces both Arrow `null` and floating-point IEEE-754 `NaN`.
- `fill_null(col, value)`: Replaces only Arrow `null`.
- `fill_nan(col, value)`: Replaces only floating-point `NaN`.

```python
penguins.mutate(
    clean_sex="fillna(sex, 'Unknown')",
    clean_mass="fillna(body_mass_g, 0, nans=True)"
)
```

### 5. Grouped Window Calculations

When combined with `.by()`, operations compute window statistics partitioned by group without collapsing table rows:

```python
(
    penguins
    .by("species")
    .mutate(
        mean_mass="mean(body_mass_g)",
        mass_dev="body_mass_g - mean(body_mass_g)",
        rank="rank(body_mass_g, descending=True)"
    )
)
```

### 6. Column Type Casting Inside `mutate`

Pytae makes inline type conversion natural and ergonomic by supporting Python's standard conversion functions (`int`, `float`, `str`, `bool`, `int32`, `float32`, etc.):

```python
# Convert types with standard functions
penguins.mutate(
    year_int="int(year)",
    mass_f32="float32(body_mass_g)",
    code_str="str(id)",
    is_large="bool(heavy_flag)"
)

# Multi-column batch casting with across syntax
penguins.mutate("(col1, col2, col3) = int(_)")
```

### 7. String Methods & Null Checks Inside `mutate`

Vectorized string operations and null/NaN predicates work directly inside `mutate` formulas:
- **String matching**: `.str.contains(pat)`, `.str.startswith(pat)` / `.str.starts_with(pat)`, `.str.endswith(pat)` / `.str.ends_with(pat)`
- **String transforms**: `.str.upper()`, `.str.lower()`, `.str.strip()`, `.str.len()`
- **Null / NaN checks**: `.is_null()` / `is_null(col)`, `.is_not_null()` / `is_not_null(col)`, `.is_nan()` / `is_nan(col)`, `.is_not_nan()`

```python
penguins.mutate(
    species_upper="species.str.upper()",
    is_gentoo="species.str.startswith('Gen')",
    has_sex="sex.is_not_null()"
)
```

### 8. Calling Custom Python, NumPy & SciPy Functions (`lambda d:`)

In Python scripts, pass a callable (`lambda d: ...`) to `mutate()` to apply any custom Python, NumPy, or SciPy function while keeping full IDE autocomplete and linter/Ruff support:

- **Vectorized / Column Functions (`lambda d: fn(d["a"], d["b"])`)**: Call the function directly on columns (`pl.Series`). Returning a `pl.Series` or `pl.Expr` attaches with **zero copy** (~0.3 ms / 100k rows), and NumPy/SciPy arrays are converted directly.
- **Row-Wise Scalar Functions (`lambda d: map(fn, d["a"], d["b"])`)**: Wrap scalar row-by-row functions (functions using Python `if/else`, `in`, `is not None`, or regex) in Python's built-in `map()` (~9–11 ms / 100k rows).

```python
import numpy as np

# 1. Row-wise scalar function (uses Python if/else, 'in', 'is not None') -> use map()
def route_shipment(origin: str, dest: str, hazmat_code: str | None) -> str:
    if origin == dest:
        return "Local Courier"
    if "-EXP-" in dest or hazmat_code is not None:
        return "Special Freight"
    return "Standard Ground"

# 2. Vectorized array function (operates on whole columns at once) -> call directly
def calc_metric(x, y):
    return x * 2.5 + np.maximum(y, 0)

df = df.mutate(
    shipping_mode=lambda d: map(route_shipment, d["origin_hub"], d["dest_code"], d["hazmat_class"]),
    metric=lambda d: calc_metric(d["a"], d["b"]),
    max_ab=lambda d: np.maximum(d["a"], d["b"]),
    adj_metric="metric + max_ab",  # String formulas can immediately reference lambda columns!
)
```

Custom callables also work with **`.by()` grouped transformations**:

```python
# Grouped custom function per sector
df = df.by("sector").mutate(
    z_spread=lambda g: (g["spread"] - g["spread"].mean()) / g["spread"].std()
)
```

---

## CLI Usage

In the CLI, `-mutate` accepts a single formula string. Multiple assignments can be separated by commas `,` or semicolons `;`:

```bash
# Basic calculation and string literal
pytae penguins.parquet -mutate "mass_kg = body_mass_g / 1000, status = 'verified'" -head 3

# Conditional branching
pytae penguins.parquet -mutate "flag = if_else(body_mass_g > 4200, 'Heavy', 'Standard')" -head 5

# Multi-column batch scaling with suffix
pytae penguins.parquet -mutate "(bill_length_mm, bill_depth_mm)_cm = _ / 10" -cols

# Grouped window calculations
pytae penguins.parquet \
  -by species \
  -mutate "species_avg = mean(body_mass_g), diff = body_mass_g - species_avg" \
  -head 5

# Type casting inside mutate
pytae data.csv -mutate "id = str(id), score = int(score)" -head 3
```

### Quoting Tips in Shell
Always enclose the entire `-mutate` specification in double quotes `""`. Use single quotes for inner string literals:
```bash
pytae data.parquet -mutate "region_label = if_else(code == 1, 'US', 'International')"
```

