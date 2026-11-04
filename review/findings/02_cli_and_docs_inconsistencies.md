# CLI and Documentation Inconsistencies Finding

This report details inconsistencies between the CLI flags, REPL behavior, docstrings, and documentation files.

---

## 1. Flag Syntax Consistency across CLI and Documentation

### Description
In historical documentation, some examples used `--select` or `--filter`. While `docs/cli_cheatsheet.md` was cleaned up, several files and help strings still contain contradictions:
1. `src/pytae/cli_help.py`: Advertises `--filter`, `--select`, `--mutate`, `--arrange`, `--sql`, `--o`, etc.
2. `src/pytae/cli.py:900-905`: Advertises `-tol / -tolerance` in help strings and epilogs, but explicitly traps and rejects `-tolerance` with `"-tolerance is not recognized; use -tol <threshold> instead."`

### Suggested Fix
- Standardize all help entries in `src/pytae/cli_help.py` to single dash: `flag="-filter CONDITIONS"`.
- Remove references to `-tolerance` in epilogs or accept `-tolerance` as an alias for `-tol`.

---

## 2. Default `dropna` Behavior: Implementation vs. Docstrings

### Description
- In `src/pytae/polars_engine.py`:
  - `df.dropna()` without arguments defaults to `how="all"` (only drops rows where *every* column is null).
  - `df.dropna("a,b")` with column arguments defaults to `how="any"` (drops rows where *any* specified column is null).
- In `src/pytae/dataframe.py` (`DataFrame.dropna` docstring) and `docs/comparison_to_pandas.md`:
  - The text equates `df.dropna()` to Pandas' default `df.dropna()`, which drops rows where *any* column is null (`how="any"`).

### Suggested Fix
Update the docstrings in `src/pytae/dataframe.py` and comparison guides to explicitly mention Pytae's smart default:
- Bare `df.dropna()` drops rows that are completely null (`how="all"`).
- Subset `df.dropna("col1, col2")` drops rows where any specified column is null (`how="any"`).

---

## 3. Substring Column Search in CLI vs REPL

### Description
- In the REPL: `-cols <query>` filters columns case-insensitively by substring (e.g., `-cols mass` shows columns containing `"mass"`).
- In the CLI: `pytae penguins.parquet -cols mass` raises:
  `ValueError: invalid order 'mass'; expected 'file', 'asc', or 'desc'`

### Expected Parity
The CLI should match the REPL: if the argument to `-cols` is not in `("file", "asc", "desc")`, treat it as a substring filter.
