# Python Library and Accessor Parity Finding

This report audits parity between top-level `pytae` functions (`pt.*`), `DataFrame` methods, and DataFrame accessors (`df.pt.*`).

---

## 1. Top-Level `pt.rename` Missing from `__all__`

### Description
`df.rename()` exists on `pytae.DataFrame` (`src/pytae/dataframe.py`), and `rename` is available in CLI (`-rename`) and accessor (`df.pt.rename`).
However, `pt.rename` is missing from `src/pytae/__init__.py` and `__all__`.

### Suggested Fix
Add `rename` to `src/pytae/__init__.py`:
```python
def rename(df: Any, *args: Any, **kwargs: Any) -> DataFrame:
    return DataFrame(df).rename(*args, **kwargs)
```
and export it in `__all__`.

---

## 2. Redundant Null-Filling Verbs ("One Obvious Way")

### Description
There are currently multiple ways to fill nulls in the Python API:
- `df.fillna(val, *cols, nans=True)`
- `df.fill_null(val, *cols)`
- `df.fill_nan(val, *cols)`
- `df.handle_missing(...)`
- `fillna(col, val)` inside `mutate()`

### Recommendation
Per Pytae's design principle ("There should be one—and preferably only one—obvious way to do it"), `fillna` should remain the canonical verb. `fill_null`, `fill_nan`, and `handle_missing` should be deprecated or kept as thin aliases.

---

## 3. Redundant `dropna` Aliases

### Description
`dropna` currently exports two public aliases: `drop_nulls` and `drop_na` across `__init__.py`, `dataframe.py`, `accessor.py`, and CLI flags.
Other aliases were deprecated across the project (e.g. `-unique` -> `-distinct`, `-qry` -> `-filter`).

### Recommendation
Standardize on `dropna` as the single canonical verb, and emit helpful hints for `drop_nulls` / `drop_na`.

