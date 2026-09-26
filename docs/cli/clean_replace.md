# CLI Feature Guide: Data Cleaning & Value Replacement

Standardize messy column headers (`-clean_columns`), replace cell values (`-replace_values`), impute missing data (`-handle_missing`), and rename columns (`-rename`).

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Header Standardization (`-clean_columns`)](#header-standardization--clean_columns)
  - [Supported Pipeline Steps](#supported-pipeline-steps)
  - [Cleaning Examples](#cleaning-examples)
- [Cell Value Replacement (`-replace_values`)](#cell-value-replacement--replace_values)
  - [Exact Matching](#exact-matching)
  - [Restricting to Columns (`c=`)](#restricting-to-columns-c)
  - [Substring Replacement (`exact=false`)](#substring-replacement-exactfalse)
- [Imputing Missing Values (`-handle_missing`)](#imputing-missing-values--handle_missing)
- [Column Renaming (`-rename`)](#column-renaming--rename)

---

## Overview & Quick Reference

| Flag | Scope | Delimiter | Description |
|---|---|---|---|
| `-clean_columns SPEC` | Column headers | `,` / `=` | Standardizes headers (strip, squeeze, fill, case, dedupe) |
| `-replace_values SPEC` | Cell contents | `old:new` | Swaps values inside cells |
| `-handle_missing [FILL]` | Cell contents | String value | Imputes `NaN` (defaults to `.` for text, `0` for numeric) |
| `-rename OLD:NEW,...` | Column headers | `old:new` | Explicitly renames column names |

---

## Header Standardization (`-clean_columns`)

Clean messy column names automatically. Options execute in this order:
1. `strip`: Remove leading and trailing whitespace.
2. `strip_special`: Remove non-alphanumeric punctuation (except `_`).
3. `squeeze`: Collapse multiple consecutive spaces into a single space.
4. `fill[=STR]`: Replace spaces with a separator (default `_`).
5. `case=lower|upper|proper`: Transform casing.
6. `dedupe`: Append suffixes (`_1`, `_2`) to disambiguate duplicated column names.

### Cleaning Examples

```bash
# Clean leading spaces, punctuation, lowercase, and replace spaces with underscores:
pytae messy.parquet -clean_columns "strip,strip_special,case=lower,fill=_"
```

**Before:**
```text
  Old Name    Score %      Status
hello world      10.5 draft_stage
    bad_val       NaN    approved
        NaN      30.2 draft_stage
```

**After:**
```text
   old_name  score_      status
hello world    10.5 draft_stage
    bad_val     NaN    approved
        NaN    30.2 draft_stage
```

---

## Cell Value Replacement (`-replace_values`)

Swap cell contents using mapping pairs `v='old:new,old2:new2'`.

### Exact Matching

```bash
pytae dataset.parquet -replace_values "v='draft_stage:in_review,bad_val:good_val'"
```

**Output:**
```text
  Old Name    Score %    Status
 hello world     10.5 in_review
    good_val      NaN  approved
         NaN     30.2 in_review
```

### Restricting to Specific Columns (`c=`)

Apply replacements only to selected columns:

```bash
pytae dataset.parquet -replace_values "c='Status',v='draft_stage:in_review'"
```

### Substring Replacement (`exact=false`)

Replace substrings anywhere inside cell text:

```bash
pytae dataset.parquet -replace_values "v='_stage:_pending',exact=false"
```

---

## Imputing Missing Values (`-handle_missing`)

Replace `NaN` values across the entire dataset. Defaults:
- Numeric columns are filled with `0`.
- String and categorical columns are filled with `.` (or your custom `FILL` string).

```bash
pytae dataset.parquet -handle_missing "UNKNOWN"
```

**Output:**
```text
  Old Name    Score %      Status
 hello world     10.5 draft_stage
     bad_val      0.0    approved
     UNKNOWN     30.2 draft_stage
```

---

## Column Renaming (`-rename`)

Rename columns explicitly at any point in the pipeline using the `old:new` mapping convention:

```bash
pytae dataset.parquet -rename "Status:review_status,Old Name:clean_name"
```

**Output:**
```text
 clean_name    Score % review_status
hello world       10.5   draft_stage
    bad_val        NaN      approved
        NaN       30.2   draft_stage
```
