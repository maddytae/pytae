# Table Reshaping (`long` & `wide`)

`pytae` replaces the confusing and inconsistent terminology of `melt`, `stack`, `unstack`, `pivot_longer`, and `pivot_wider` with two intuitive English opposites:
- **`long()`**: Turns wide tables into tall records (unpivoting).
- **`wide()`**: Spreads tall records into wide columns (1:1 pivoting).

Both methods share the identical, clean `r=` (row keys), `c=` (columns), and `v=` (values) vocabulary.

---

## Rosetta Stone: Python vs. CLI

| Reshape Type | Python Library (`pytae`) | Command Line (`pytae CLI`) |
|:---|:---|:---|
| **Wide to Long (`long`)** | `df.long(id_vars="id", cols=["q1", "q2"])` | `-long "id_vars=id, cols='q1,q2'"` |
| **Custom Names in `long`** | `df.long(id_vars="id", cols=["q1", "q2"], var_name="quarter", value_name="sales")` | `-long "id_vars=id, cols='q1,q2', var_name=quarter, value_name=sales"` |
| **Long to Wide (`wide`)** | `df.wide(r="id", c="quarter", v="sales")` | `-wide "r=id, c=quarter, v=sales"` |

---

## Python Library Usage

### 1. Melting to Long Format (`long`)

```python
import pytae as pt
import polars as pl

wide_df = pt.DataFrame({
    "id": [1, 2],
    "q1": [100, 200],
    "q2": [150, 250]
})

long_df = wide_df.long(
    id_vars="id",
    cols=["q1", "q2"],
    var_name="quarter",
    value_name="revenue"
)
```

**Output:**
```text
┌─────┬─────────┬─────────┐
│ id  ┆ quarter ┆ revenue │
│ --- ┆ ---     ┆ ---     │
│ i64 ┆ str     ┆ i64     │
╞═════╪═════════╪═════════╡
│ 1   ┆ q1      ┆ 100     │
│ 1   ┆ q2      ┆ 150     │
│ 2   ┆ q1      ┆ 200     │
│ 2   ┆ q2      ┆ 250     │
└─────┴─────────┴─────────┘
```

### 2. Spreading to Wide Format (`wide`)

```python
reconstructed = long_df.wide(
    r="id",
    c="quarter",
    v="revenue"
)
```

---

## CLI Usage

In the CLI, `-long` and `-wide` allow quick schema reshaping directly in shell pipelines:

```bash
# Melt quarter columns into long rows
pytae quarterly_sales.csv -long "id_vars=id, cols='q1,q2', var_name=quarter, value_name=revenue" -o long_sales.parquet

# Spread back into wide table
pytae long_sales.parquet -wide "r=id, c=quarter, v=revenue" -head 5
```
