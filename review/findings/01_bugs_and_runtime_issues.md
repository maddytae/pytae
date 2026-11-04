# Bugs and Runtime Issues Finding

This report details confirmed bugs and runtime edge cases in `pytae` v3.13.3, identifying reproduction steps, current vs expected behavior, and suggested fixes.

---

## 1. CLI Help Advertises Double-Hyphen Flags While Parser Strictly Rejects Them

### Description
In `src/pytae/cli_help.py`, all 33 keyword help topics advertise double-hyphen flags alongside single-hyphen flags in their `flag` headers (e.g. `flag="-filter, --filter CONDITIONS"`, `flag="-select, --select SPEC"`, `flag="-sql, --sql QUERY"`).
However, `src/pytae/cli.py` (`_check_double_dash`) strictly enforces single-dash flags, rejecting any double-hyphen flag with:
```
pytae: error: '--<flag>' uses double hyphens; pytae uses single hyphen '-<flag>'.
```

### Reproduction
```bash
pytae penguins.parquet --filter "body_mass_g > 3000"
# or
pytae penguins.parquet --select "species,island"
```

### Observed Behavior
Exits with code 2:
```text
pytae: error: '--filter' uses double hyphens; pytae uses single hyphen '-filter'.
```

### Expected Behavior
Help strings should match parser rules. Either:
1. Update `src/pytae/cli_help.py` headers to show `flag="-filter CONDITIONS"` (single dash), OR
2. Allow double hyphens as transparent aliases in `src/pytae/cli.py` so user habits from standard POSIX CLIs don't result in fatal errors.

---

## 2. `.pt.glimpse()` Breaks Fluent Method Chaining on Polars and Pandas Frames

### Description
Calling `df.glimpse()` on a `pytae.DataFrame` returns `self` (`pytae.DataFrame`), allowing fluent chaining:
```python
df.glimpse().filter("body_mass_g > 3000").head(5)
```
However, in `src/pytae/accessor.py` (line 173), `_BasePtAccessor.glimpse()` returns `self._obj` (a raw `polars.DataFrame`, `polars.LazyFrame`, or `pandas.DataFrame`).

### Reproduction
```python
import polars as pl
import pytae as pt

pl_df = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
pl_df.pt.glimpse().mutate("c = a + b")
```

### Observed Behavior
Raises `AttributeError` because the returned Polars DataFrame has no `.mutate()` method.

### Expected Behavior
`_BasePtAccessor.glimpse()` should return `DataFrame(self._obj)` to allow seamless chaining of Pytae verbs.

---

## 3. Duplicate Bar Column When Chaining `-freq` and `-bar`

### Description
In `src/pytae/cli_run.py`, `-freq <col>` produces a 3-column table:
`[<col>, "Count", "Distribution"]`
where `"Distribution"` already contains an inline Unicode horizontal bar chart and percentage (e.g. `████████████ (44.2%)`).
When a user follows the advertised recipe in documentation (`pytae penguins.parquet -freq species -bar`), `-bar` appends an extra fourth `"Bar"` column containing a redundant identical bar chart.

### Suggested Fix
If the incoming DataFrame already contains `"Distribution"` from `-freq`, `-bar` should either update/replace the column or treat it as a no-op instead of creating a duplicate bar column.

---

## 4. `save_code` Path Parent Directory Creation in REPL

### Description
In `src/pytae/repl.py`, setting `set save_code = subfolder/code.txt` and exiting with `exit -s` attempts to write the session code file directly with `open(path, "w")`. If `subfolder/` does not exist, it raises an unhandled `FileNotFoundError`.

### Suggested Fix
Ensure `Path(path).parent.mkdir(parents=True, exist_ok=True)` is called prior to opening the file.

