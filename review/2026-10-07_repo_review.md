# pytae Repository Review

**Date:** 2026-10-07  
**Commit reviewed:** `f215b15` (master, 1 commit ahead of `origin/master`)  
**Version in `pyproject.toml`:** 3.8.1

## Baseline health

| Check | Result |
|---|---|
| `pytest tests/` | 629 passed, 70 warnings (all expected deprecation warnings) |
| `scripts/run_notebooks.py` | 12/12 notebooks `ok` |
| `mypy src` | No issues (20 files) |
| `ruff check src tests` | **12 errors**, all import ordering, all auto-fixable (`ruff check --fix`) |

The code is in good shape overall. The main risk is in the new grouping design. Grouping is stored in `df.attrs["_pt_by"]`, and pandas copies and saves `attrs` in places pytae doesn't control. Every issue below was reproduced with a script against the current code.

---

## 🔴 Critical: grouping state leaks and changes results without warning

### C1. `by()` changes the caller's DataFrame in place

`src/pytae/by.py` writes `df.attrs["_pt_by"]` and returns **the same object**.

```python
p = pt.sample("penguins")
p.pt.by("species")            # result discarded
p.pt.agg("mean")              # -> 3 rows (per species), not the expected 1-row summary
```

- Probe: `p.pt.by("species") is p` → `True`.
- This breaks Core Principle #5 ("Non-Destructive: all library verbs return copies and never mutate inputs").
- In notebooks, one exploratory `.pt.by(...)` call quietly groups the shared `penguins`/`tips` variable for every later cell.

### C2. Verbs clear grouping on their *input*, and the functional and accessor forms behave differently

- `arrange.pick()` (lines 194–197) and `accessor.agg()` (lines 247–250) `del df.attrs["_pt_by"]` on the **input** frame. That is another hidden in-place change.
- Functional `pt.agg()` does **not** clear grouping. The input stays grouped forever:

```python
p = pt.sample("penguins")
pt.agg(pt.by(p, "species"), "mean")
p.attrs        # {'_pt_by': ('species',)}  <- still grouped
```

This breaks the "dual calling convention" promise that `pt.verb(df)` and `df.pt.verb()` behave the same.

### C3. Grouping is saved to Parquet files and comes back on read (library and CLI)

pandas ≥ 2.1 writes `df.attrs` into Parquet metadata, so a grouped frame produces a "secretly grouped" file.

```bash
pytae penguins.parquet -by species -mutate "kg = body_mass_g / 1000" -o out.parquet
pytae out.parquet -agg "n=n"
#   species   n          <- expected a single whole-table row; no -by was given
#    Adelie 152
# Chinstrap  68
#    Gentoo 124
```

The same happens in Python with `df.to_parquet()` → `pd.read_parquet()` → `.pt.agg()`. **This produces wrong results and nothing in the output says why.** A user who gets the file later has no way to see why a plain `-agg` is grouped.

### C4. Grouping carries through some pandas operations but not others

Because of pandas `__finalize__`, `_pt_by` survives boolean indexing, `.head()`, `.copy()`, `pt.filter`, `pt.distinct`, and `pt.mutate`. It is dropped by `pd.concat`, `pt.pivot`, and others. Whether grouping is carried forward is an accident of pandas internals and is not documented. If you then select away a grouping column, the next step fails with a confusing error:

```python
pt.sample("penguins").pt.by("species").pt.select("island", "body_mass_g").pt.agg("mean")
# KeyError: "agg(): group column 'species' not found in DataFrame"
```

### Recommended fix for C1–C4 (one coherent change)

1. **`by()` / `ungroup()` return a shallow copy:**
   ```python
   out = df.copy(deep=False)
   out.attrs = {**df.attrs, "_pt_by": tuple(valid_cols)}
   return out
   ```
2. **No verb ever edits `df.attrs` on its input.** Clear grouping only on the result. Move the clearing into the core `agg()` function so the functional and accessor forms behave the same.
3. **Remove `_pt_by` at I/O boundaries:**
   - Remove it before every write in the CLI writers / `-o` and in `to_clip`.
   - Ignore or remove it after every read in `readers.py`.
   - Optionally, register a cleanup step so `to_parquet` never saves it.
4. **Write down the carry-forward policy** (e.g. "grouping survives `filter`, `mutate`, `arrange`, `distinct`; cleared by `agg`, `pick`, `pivot`, `long`, `wide`, `sql`, `select` that drops a group column"). Enforce it explicitly in each verb rather than relying on pandas.
5. **Add regression tests:**
   - The input is unchanged after `by`, `agg`, `pick`, and `mutate`.
   - Functional and accessor results are the same.
   - A Parquet round-trip does not restore grouping.
   - The CLI `-o` output is ungrouped.
   - Note: `tests/test_verbs_v39.py::test_ungroup_clears_by` currently *depends on* the in-place change and will need rewriting.

---

## 🟠 High: API consistency with the "one and only one way" rule

- **H1. `by()` still accepts a comma-separated string.** `df.pt.by("species, island")` works (`by.py` lines 49–53), even though the docstring says only positional names are accepted. Either reject it with a hint, or document it. Right now there are two ways.
- **H2. Breaking change shipped as a patch version.** Removing `by=` from `mutate`/`pick`/`agg` breaks existing user code, but the version stays `3.8.1`. Under semver this is at least a minor bump (and arguably a major one). I understand 3.8.1 is a deliberate constraint, so this is flagged only as a release-communication risk.
- **H3. The changelog has no entry for these changes.** `changelog.md` stops at `[3.8.0]`. Missing items:
  - `filter`/`pick`/`distinct`
  - standalone `by`/`ungroup`
  - the removal of `by=`
  - the deprecations

  Meanwhile, the reference manual (`generate_reference.py` line 827) says *"Pytae v3.9 standardizes…"*, which contradicts the 3.8.1 version.

---

## 🟡 Medium: documentation and help text that no longer matches the code

| Location | Issue |
|---|---|
| `src/pytae/by.py` docstring | Mentions `.pt.slice_max()/.pt.slice_min()` and "unless explicitly overridden". Overriding is no longer possible. |
| `cli_help.py` `"by"` entry (lines 338–354) | Summary, examples, and see-also still use `-slice_max`/`-slice_min` instead of `-pick`. |
| `cli_help.py` `"slice_min"` | Not marked deprecated, unlike `slice_max`. |
| `cli_help.py` `select`/`output`/`shape` entries | Examples and see-also still use deprecated `-qry`. |
| `docs/library.md` §3 (lines 144, 147) | Still shows `pt.mutate(..., by="species")` / `by="group"`. Those calls now raise `TypeError`. |
| `docs/library.md` table | "grouped transforms `by=`" (Mutating row) and "`by=`" (Picking row) are outdated wording. |
| `docs/library.md` §1 example | `pt.agg(subset, "species", "mean")`. In the new API, the positional `"species"` is parsed as an aggregation spec, not a grouping. |

Suggestion: add a CI check that greps docs, notebooks, and help text for `by=` inside verb calls and for `-qry`/`-slice_max`/`-dedupe` outside deprecation sections.

---

## 🟢 Low / housekeeping

- **Ruff:** 12 import-ordering errors (e.g. `qry.py` imports). Fix with `ruff check --fix`. Consider adding ruff to the pre-commit hook or CI so it can't regress.
- **Notebook cell IDs:** notebooks edited by script produced `MissingIDFieldWarning`. Run `nbformat.validator.normalize` across all notebooks in `run_notebooks.py`.
- **`mutate()` caller-frame lookup** skips every frame whose module name starts with `"pytae"`. A user module named e.g. `pytae_utils` would be skipped by mistake. Match `== "pytae"` or `startswith("pytae.")` instead.
- **`.gitignore`** ignores `.review/` (with a dot), not `review/`. Decide whether this `review/` folder should be committed or ignored.
- **Module size:** `plotting.py` (1205 lines) and `cli_run.py` (972 lines) are getting large. Splitting them is optional and not urgent.

---

## What's working well

- **Error messages:** fuzzy "did you mean" suggestions, and explicit `TypeError`s that point users to the canonical form (e.g. passing `by=` to verbs).
- **Tests:** a broad suite (620+ test functions across library and CLI) and executable notebooks used as doc tests. Together they make the docs trustworthy.
- **Deprecations:** clean aliases (`qry`, `slice_max/min`, `dedupe`) that warn and still work.
- **Typing:** `mypy` passes on the whole package.
- **Reference manual:** a generated, self-contained manual that includes docs, notebooks, source, and tests.

---

## Prioritized action list

1. **Fix C1–C4:** copy-on-`by`, no input edits, remove grouping at I/O, functional/accessor parity, plus tests. This is a correctness issue.
2. Update docs and help text that still use `by=` inside verbs (H-table above). Users copying from `library.md` will hit `TypeError`.
3. Resolve the comma-string ambiguity in `by()` (H1).
4. Add a changelog entry and settle the "v3.9" vs 3.8.1 wording (H2/H3).
5. Run `ruff --fix`, normalize notebook IDs, and tighten the `mutate` frame filter.
