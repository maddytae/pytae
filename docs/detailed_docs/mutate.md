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
   df.mutate(a=lambda d: d["x"] * 2, b="a + 10", c=lambda d: d["b"] * 3)
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
df1 = penguins.mutate(body_mass_kg="body_mass_g / 1000", status="'active'", verified=True)

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
# Binary condition returning literals
penguins.mutate(size_category="if_else(body_mass_g > 4000, 'Large', 'Normal')")

# Dynamic column selection: pick cola if var is 'yes', else colb
df.mutate("colx = if_else(var == 'yes', cola, colb)")

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

# Complex domain branching with string matching, logical 'or', and null checks
deals.mutate(
    tranche_type="""
    case_when(
        (deal_identifier == tranche_id, 'Main Tranche'),
        (tranche_id.str.contains('-COL-') or collateral_class.is_not_null(), 'Collateral'),
        'Guarantor'
    )
    """
)
```

#### A. Referencing External Python Variables (`@var`)

Use the `@` prefix to reference variables from the surrounding Python scope directly inside formulas, `if_else`, and `case_when`:

```python
# External threshold variable
cutoff = 4200
penguins.mutate("size = if_else(body_mass_g >= @cutoff, 'Large', 'Normal')")

# External string variable selecting between columns
var = "yes"
df.mutate("colx = if_else(@var == 'yes', cola, colb)")
```

> [!NOTE]
> **Why `@` is required for Python variables:**
> In Pytae formula strings, bare unquoted identifiers (`cola`, `colb`, `var`) always resolve to **DataFrame column names**.
> The `@` prefix (e.g. `@var`, `@cutoff`) explicitly signals an external Python variable from your script or notebook.
> This eliminates ambiguity:
> - `var` = column in the DataFrame
> - `@var` = local Python variable
> It also guards against silent bugs where a misspelled column name might otherwise silently resolve to a variable in scope instead of raising a clear `KeyError`.

#### B. Script-Level Toggles vs. Row-Level `if_else`

If `var` is a fixed script parameter (e.g. `var = 'yes'`), every row will take the same branch. While `if_else(@var == 'yes', cola, colb)` is fully supported, resolving the target column name directly in Python avoids evaluating a vectorized conditional over millions of rows:

```python
var = "yes"

# Dynamic column aliasing via f-string (zero-cost column pointer)
target_col = "cola" if var == "yes" else "colb"
df.mutate(f"colx = {target_col}")
```

#### C. Logical Operators in Formulas: `or` vs. `|`

Inside Pytae formula strings (`mutate`, `filter`, CLI), you can use natural English `or` and `and`:

```python
# Clean & readable - no extra parentheses required
df.mutate("flag = if_else(mass > 4000 or species == 'Gentoo', 'Highlight', 'Normal')")

# If you use '|' or '&', you MUST wrap each comparison in parentheses
# due to Python's bitwise operator precedence:
df.mutate("flag = if_else((mass > 4000) | (species == 'Gentoo'), 'Highlight', 'Normal')")
```

### 4. Smart Missing Imputation Inside `mutate`

Pytae provides vectorized missing value imputation directly inside `mutate`:
- `fillna(col, value)` / `col.fillna(value)`: Replaces both Arrow `null` and floating-point IEEE-754 `NaN`.

```python
penguins.mutate(
    clean_sex="fillna(sex, 'Unknown')",
    clean_mass="fillna(body_mass_g, 0)",
)
```

### 5. Vectorized Value Mapping & Recoding (`map`)

Use `map(col, mapping[, fallback])` inside `mutate()` to replace cell values using a dictionary mapping. It executes vectorized in the Polars engine with **Zero Data Loss by default**:

> [!NOTE]
> **Formula `map()` is strictly for dictionary value recoding, not for executing Python functions.**
> - Use formula `map(col, {'old': 'new'})` to recode categorical or scalar values via a dictionary lookup.
> - To execute custom Python/NumPy logic or row-wise transformations, pass a callable `lambda d:` as covered in [Section 9](#9-calling-custom-python-numpy--scipy-functions-lambda-d).

```python
# 1. Two-argument: recode mapped keys, preserve unmapped values intact
penguins.mutate(
    species_code="map(species, {'Adelie': 'AD', 'Gentoo': 'GEN'})",
)

# 2. Three-argument with literal fallback: replace unmapped rows with a constant
penguins.mutate(
    species_code="map(species, {'Adelie': 'AD'}, 'Other')",
)

# 3. Three-argument with column fallback: pull replacement from another column
deals.mutate(
    party_code="map(deal_type, {'Direct': 'DIR'}, broker_code)",
)

# 4. Explicit null fallback: explicitly set unmapped rows to null
penguins.mutate(
    strict_code="map(species, {'Adelie': 'AD'}, None)",
)

# 5. Multi-column batch mapping with across syntax
df.mutate("(cat_a, cat_b) = map(_, {'0': 'Inactive', '1': 'Active'})")
```

```bash
# In CLI:
pytae penguins.parquet -mutate "code = map(species, {'Adelie': 'AD'})" -head 5
pytae penguins.parquet -mutate "code = map(species, {'Adelie': 'AD'}, 'Other')" -head 5
pytae penguins.parquet -mutate "code = map(species, {'Adelie': 'AD'}, island)" -head 5
```

### 6. Grouped Window & Time-Series Calculations

When combined with `.by()`, operations compute window statistics partitioned by group without collapsing table rows:

#### A. Initial & Final Group Boundaries (`first`, `last`)
Compute drifts and baselines from the first or last observation in each group (e.g. initial patient vitals or opening stock prices):

```python
stocks.by("ticker").mutate(
    baseline="first(price)",
    drift_from_start="price - first(price)",
    final_price="last(price)",
)
```

#### B. Sequential Shifts, Differences & Growth Rates (`shift`, `lag`, `lead`)
Instead of duplicating verbs, Pytae provides `shift()` (with `lag` and `lead` aliases) for time-series operations:
- **Difference (`diff`)**: `price - shift(price, 1)`
- **Percentage Change / Growth (`pct_change`)**: `price / shift(price, 1) - 1`
- **Future Lookahead (`lead`)**: `lead(price, 1)` or `shift(price, -1)`

```python
stocks.by("ticker").mutate(
    prev_price="shift(price, 1)",
    diff="price - shift(price, 1)",
    daily_return="price / shift(price, 1) - 1",
    next_price="lead(price, 1)",
)
```

#### C. Cumulative Computations (`cumsum`, `cumprod`, `cummin`, `cummax`)
Cumulative statistics accumulate along group order:

```python
sales.by("region").mutate(
    running_total="amount.cumsum()",
    running_peak="amount.cummax()",
)
```

#### D. Grouped Window Statistics & Deviations
```python
penguins.by("species").mutate(
    mean_mass="mean(body_mass_g)",
    mass_dev="body_mass_g - mean(body_mass_g)",
    rank="rank(body_mass_g, descending=True)",
)
```

#### E. Moving Averages & Rolling Windows (via `-sql` or Polars)
To avoid unnecessary function proliferation in `mutate()`, rolling computations (e.g. 7-day moving averages, rolling volatility) are performed via standard ANSI SQL window frames on the CLI or Polars in Python:

```bash
# In CLI: Full SQL window frame support with -sql
pytae stocks.parquet -sql "
  SELECT *, 
         AVG(price) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7
  FROM data
"
```

```python
# In Python: Transparent Polars expression delegation
import polars as pl

stocks.with_columns(pl.col("price").rolling_mean(window_size=7).over("ticker"))
```

#### F. Single-Shot Grouping (Why `ungroup()` is Not Needed)
In Pytae, `.by()` establishes an **ephemeral, single-shot grouping context** for the immediate next operation. Once `mutate()` (or `agg()` / `pick()`) executes, it automatically consumes the grouping and returns a standard, flat, ungrouped `DataFrame`. 

Because grouping is never "sticky" (unlike R's `dplyr`), you never need to call `ungroup()`. You can freely chain from grouped mutations directly into overall table calculations or new grouping keys:

```python
result = (
    sales
    .by("region").mutate(region_avg="mean(amount)")    # 1. Group-level mean
    .mutate(overall_avg="mean(amount)")                 # 2. Automatically overall table mean
    .by("product").mutate(product_avg="mean(amount)")   # 3. Newly grouped by product
)
```

### 7. Column Type Casting Inside `mutate`

Pytae makes inline type conversion natural and ergonomic by supporting Python's standard conversion functions (`int`, `float`, `str`, `bool`, `int32`, `float32`, etc.):

```python
# Convert types with standard functions
penguins.mutate(year_int="int(year)", mass_f32="float32(body_mass_g)", code_str="str(id)", is_large="bool(heavy_flag)")

# Multi-column batch casting with across syntax
penguins.mutate("(col1, col2, col3) = int(_)")
```

### 8. String Methods & Null Checks Inside `mutate`

Vectorized string operations and null/NaN predicates work directly inside `mutate` formulas:
- **String matching**: `.str.contains(pat)`, `.str.startswith(pat)` / `.str.starts_with(pat)`, `.str.endswith(pat)` / `.str.ends_with(pat)`
- **String transforms**: `.str.upper()`, `.str.lower()`, `.str.strip()`, `.str.len()`
- **Null / NaN checks**: `.is_null()` / `is_null(col)`, `.is_not_null()` / `is_not_null(col)`, `.is_nan()` / `is_nan(col)`, `.is_not_nan()`

```python
penguins.mutate(
    species_upper="species.str.upper()", is_gentoo="species.str.startswith('Gen')", has_sex="sex.is_not_null()"
)
```

### 9. Calling Custom Python, NumPy & SciPy Functions (`lambda d:`)

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
df = df.by("sector").mutate(z_spread=lambda g: (g["spread"] - g["spread"].mean()) / g["spread"].std())
```

> [!IMPORTANT]
> **Summary: When to use Formula `map()` vs. `lambda d:`**
>
> | Goal | Mechanism | Example |
> |---|---|---|
> | **Dictionary Value Recoding** | Formula `map(col, dict[, fallback])` | `df.mutate(code="map(species, {'Adelie': 'AD'})")` |
> | **Vectorized Array / Math Function** | `lambda d: func(d['x'], d['y'])` | `df.mutate(metric=lambda d: np.maximum(d['a'], d['b']))` |
> | **Scalar Row-Wise Python Function** | `lambda d: map(func, d['x'], d['y'])` | `df.mutate(label=lambda d: map(classify, d['origin'], d['dest']))` |

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

# Time-series differences, lag, and percentage returns per group
pytae stocks.parquet \
  -by ticker \
  -mutate "prev = shift(price, 1), diff = price - shift(price, 1), ret = price / shift(price, 1) - 1" \
  -head 5

# Baseline drift from first observation
pytae stocks.parquet \
  -by ticker \
  -mutate "baseline = first(price), gain = price - first(price)" \
  -head 5

# Type casting inside mutate
pytae data.csv -mutate "id = str(id), score = int(score)" -head 3
```

### Quoting Tips in Shell
Always enclose the entire `-mutate` specification in double quotes `""`. Use single quotes for inner string literals:
```bash
pytae data.parquet -mutate "region_label = if_else(code == 1, 'US', 'International')"
```

