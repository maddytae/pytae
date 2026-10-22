from pathlib import Path

import nbformat as nbf

nb = nbf.v4.new_notebook()

cells = []

# Cell 0: Header & Comprehensive Reference
cells.append(nbf.v4.new_markdown_cell("""# `filter` — Comprehensive Reference

`filter` filters a DataFrame using intuitive CLI-style string expressions or programmatic dictionaries.

Under the hood, `filter` compiles conditions into high-performance Polars expressions evaluated directly in native C++/Rust memory.

### Calling Styles

`filter` supports two clean, unambiguous calling styles:

- **String expressions** (matches CLI `-filter` syntax; handles spaces directly):
  `df.filter("[bill length mm] > 40 and species == 'Adelie'")`
- **Dictionaries** (ideal for dynamic programmatic keys and Option 1 / Option 2 ranges):
  `df.filter({"bill length mm": "> 40", "species": "Adelie"})`
  `df.filter({"body_mass_g": ("between", 3500, 4000)})`
  `df.filter({"body_mass_g": ((">=", 3500), ("<=", 4000))})`
- **Top-level library verb**:
  `pt.filter(df, "species == 'Adelie' and body_mass_g > 5000")`

> [!IMPORTANT]
> **Why `pytae` Strictly Enforces `==` and Disallows Kwargs**:
> In Python syntax, keyword arguments like `df.filter(species="Adelie")` force the use of a single `=`. In `pytae`, single `=` is reserved exclusively for column assignments in `-mutate`. To prevent subtle bugs and ensure **"one and only one obvious way"**, `filter()` strictly requires `==` and raises an immediate `TypeError` if keyword arguments are passed.

---

### Comprehensive Reference Table

| Category | Example Syntax | Meaning / Target |
|---|---|---|
| **Equality** | `"species == 'Adelie'"` or `{"species": "Adelie"}` | Exact equality match (`==` strictly enforced; single `=` raises error) |
| **Inequality** | `"species != 'Adelie'"` or `{"species": ("!=", "Adelie")}` | Inequality match |
| **Relational Operators** | `"body_mass_g > 5000"` or `{"body_mass_g": (">", 5000)}` | `>`, `>=`, `<`, `<=`, `==`, `!=` |
| **Set Membership** | `"species in ['Adelie', 'Gentoo']"` or `{"species": ['Adelie', 'Gentoo']}` | In candidate set / list |
| **Exclusion** | `"sex not in ['Male']"` or `{"sex": ("not in", ['Male'])}` | Not in candidate set |
| **Boolean AND** | `"species == 'Gentoo' and body_mass_g > 4500"` | Logical conjunction (comma `,` and bitwise `&` disallowed) |
| **Boolean OR** | `"island == 'Dream' or island == 'Torgersen'"` | Logical disjunction (bitwise `\\|` disallowed) |
| **Grouping / Precedence** | `"(species == 'Adelie' or species == 'Chinstrap') and mass > 4000"` | Arbitrary nested boolean logic with parentheses |
| **Range Option 1 (`between`)** | `{"body_mass_g": ("between", 3500, 4000)}` | Inclusive range (`min <= x <= max`) via Polars `.is_between()` |
| **Range Option 2 (operator tuples)** | `{"body_mass_g": ((">=", 3500), ("<=", 4000))}` | Multiple conditions on same column via clean `(op, val)` pairs |
| **String Range Expression** | `"body_mass_g >= 3500 and body_mass_g <= 4000"` | Explicit boolean bounds in string expression |
| **Columns with Spaces** | `"[bill length mm] > 40"` or `{"bill length mm": (">", 40)}` | Spaced column syntax (brackets in strings, plain keys in dicts) |
| **String Prefixes/Suffixes** | `{"species": ("startswith", "Ad")}` or `{"species": ("endswith", "strap")}` | String prefix / suffix search |
| **Multiple Prefixes/Suffixes** | `{"species": ("startswith", ["Ad", "Ge"])}` | Matches any prefix / suffix in sequence |
| **String Substring / Regex** | `{"species": ("contains", "adel")}` or `{"species": ("regex", r"oo")}` | Substring match or regex search |
| **Null & NaN Checks** | `"sex.is_not_null()"`, `{"sex": "is_null()"}`, `"score.is_nan()"`, `{"score": "is_nan()"}` | Missing data (`null`) and IEEE 754 float NaNs (`NaN`) via universal method tokens (expressions & dicts) |
| **Column-to-Column** | `"exposure > limit"` or `"tranche_id == deal_id"` | Compare two columns using bare column names |
| **Variable Injection** | `"exposure > @threshold and tranche == col(@target_col)"` | External scalar (`@var`) and column (`col(@var)`) references |

---"""))

# Cell 1: Setup / Imports
cells.append(nbf.v4.new_code_cell("""import sys, os
_src = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'src'))
if not os.path.exists(_src): _src = os.path.abspath(os.path.join(os.getcwd(), '..', 'src'))
if _src not in sys.path: sys.path.insert(0, _src)

import pytae as pt

penguins = pt.sample_data['penguins']
tips = pt.sample_data['tips']
titanic = pt.sample_data['titanic']
print("Loaded sample datasets:", list(pt.sample_data.keys()))"""))

# Cell 2: Section 1 Markdown
cells.append(nbf.v4.new_markdown_cell("""## 1. Primary Calling Styles: String Expressions and Dictionaries

`filter()` accepts conditions as string expressions matching the CLI `-filter` syntax, or plain dictionaries for programmatic filters. Both direct method chaining (`df.filter(...)`) and the top-level library verb (`pt.filter(df, ...)`) are supported."""))

# Cell 3: String expressions
cells.append(nbf.v4.new_code_cell("""# 1. String expressions — clean, readable, matches pytae CLI -filter syntax
# Uses '==' for equality and 'and' for logical conjunction
(
    penguins
    .filter("species == 'Adelie' and island == 'Dream'")
    .head(5)
)"""))

# Cell 4: Plain dictionaries
cells.append(nbf.v4.new_code_cell("""# 2. Plain dictionaries — ideal for programmatic pipelines or dynamic key mapping
(
    penguins
    .filter({"species": "Adelie", "island": "Dream"})
    .head(5)
)"""))

# Cell 5: Multiple string conditions
cells.append(nbf.v4.new_code_cell("""# 3. Composing multiple conditions — either chained or passed as multiple positional arguments
(
    penguins
    .filter("body_mass_g > 4000", "island == 'Biscoe'")
    .head(5)
)"""))

# Cell 6: Top-level function
cells.append(nbf.v4.new_code_cell("""# 4. Top-level function pt.filter(df, ...) — works identically to DataFrame method
pt.filter(penguins, "species == 'Gentoo' and body_mass_g > 5000").head(5)"""))

# Cell 7: Section 2 Markdown
cells.append(nbf.v4.new_markdown_cell("""## 2. Relational Comparisons (`==`, `!=`, `<`, `>`, `<=`, `>=`)

Comparison filters can be written directly in string expressions or as operator tuples inside dictionaries:
- String expressions: `"body_mass_g > 5000"`, `"species == 'Gentoo'"`
- Dictionary with operator tuples: `{"body_mass_g": (">", 5000)}`, `{"island": ("!=", "Dream")}`

> [!IMPORTANT]
> **Strict Equality Enforcement**: In `pytae`, equality comparisons in filter strings strictly require `==`. Single `=` is reserved exclusively for column assignments in `-mutate`. Using single `=` in filter expressions raises an immediate diagnostic error."""))

# Cell 8: Numeric comparisons
cells.append(nbf.v4.new_code_cell("""# Numeric comparisons via string expressions
(
    penguins
    .filter("body_mass_g > 5000 and flipper_length_mm >= 220")
    .select('species', 'island', 'body_mass_g', 'flipper_length_mm')
    .head(5)
)"""))

# Cell 9: Dictionary operator tuples
cells.append(nbf.v4.new_code_cell("""# Dictionary with operator tuples: (op, value)
(
    penguins
    .filter({"body_mass_g": (">", 5500), "island": ("!=", "Dream")})
    .select('species', 'island', 'body_mass_g')
    .head(5)
)"""))

# Cell 10: Strict bounds
cells.append(nbf.v4.new_code_cell("""# Multiple comparisons in string expressions
(
    penguins
    .filter("body_mass_g <= 3000 and bill_length_mm < 37")
    .select('species', 'island', 'bill_length_mm', 'body_mass_g')
    .head(5)
)"""))

# Cell 11: Section 3 Markdown
cells.append(nbf.v4.new_markdown_cell("""## 3. Set Membership (`in` and `not in`)

To match against a list of candidate values:
- Use SQL/Python-style `in` or `not in` in string expressions: `"species in ['Adelie', 'Chinstrap']"`
- Pass a candidate list or exclusion tuple in a dictionary: `{"species": ['Adelie', 'Chinstrap']}`, `{"sex": ("not in", ['Male'])}`"""))

# Cell 12: Membership in strings
cells.append(nbf.v4.new_code_cell("""# Set membership via string expression
(
    penguins
    .filter("species in ['Adelie', 'Chinstrap'] and island in ['Dream', 'Biscoe']")
    .by('species', 'island')
    .agg("n = count, mean_mass = body_mass_g:mean")
)"""))

# Cell 13: Membership and exclusion in strings
cells.append(nbf.v4.new_code_cell("""# 'in' and 'not in' inside string expressions
(
    penguins
    .filter("species in ['Adelie', 'Gentoo'] and island not in ['Torgersen']")
    .by('species', 'island')
    .agg("n = count")
)"""))

# Cell 14: Membership and exclusion in dictionaries
cells.append(nbf.v4.new_code_cell("""# Membership and exclusion using dictionary syntax
(
    penguins
    .filter({
        "species": ("not in", ['Gentoo']),
        "island": ['Dream', 'Torgersen'],
    })
    .select('species', 'island', 'sex', 'body_mass_g')
    .head(5)
)"""))

# Cell 15: Section 4 Markdown
cells.append(nbf.v4.new_markdown_cell("""## 4. Boolean Logic: `and`, `or`, and Parentheses `(...)`

`pytae` supports rich boolean expressions in filter strings with:
- `and` for logical conjunction
- `or` for logical disjunction
- Arbitrary nesting with parentheses `(...)` for explicit precedence control

> [!NOTE]
> Following the Zen of Python (*"There should be one-- and preferably only one --obvious way to do it"*), `pytae` strictly uses `and` and `or`. Bitwise `&` and `|` are disallowed, and commas `,` are strictly punctuation for function arguments and lists, not boolean operators."""))

# Cell 16: Conjunction
cells.append(nbf.v4.new_code_cell("""# Logical conjunction with 'and'
(
    penguins
    .filter("species == 'Gentoo' and body_mass_g > 5500 and sex == 'Female'")
    .select('species', 'island', 'sex', 'body_mass_g')
    .head(5)
)"""))

# Cell 17: Disjunction
cells.append(nbf.v4.new_code_cell("""# Logical disjunction with 'or'
(
    penguins
    .filter("island == 'Dream' or island == 'Torgersen'")
    .by('island')
    .agg("n = count")
)"""))

# Cell 18: Nested parentheses
cells.append(nbf.v4.new_code_cell("""# Combining 'or' and 'and' with parentheses for precedence:
# Keep Adelie or Chinstrap penguins that weigh over 4000g:
(
    penguins
    .filter("(species == 'Adelie' or species == 'Chinstrap') and body_mass_g > 4000")
    .select('species', 'island', 'sex', 'body_mass_g')
    .head(6)
)"""))

# Cell 19: Complex nested boolean expression
cells.append(nbf.v4.new_code_cell("""# Complex nested logic:
# (Gentoo on Biscoe) OR (Adelie on Dream), with body mass >= 3500
(
    penguins
    .filter("((species == 'Gentoo' and island == 'Biscoe') or (species == 'Adelie' and island == 'Dream')) and body_mass_g >= 3500")
    .by('species', 'island')
    .agg("n = count, mean_mass = body_mass_g:mean")
)"""))

# Cell 20: Section 5 Markdown
cells.append(nbf.v4.new_markdown_cell("""## 5. Range & Interval Filtering: Option 1 and Option 2

Previous versions of data tools frequently used mathematical interval strings like `'[3000, 4000]'` or `'(3000, 4000)'`. In modern `pytae`, string bracket notation was dropped to eliminate ambiguity with Python list literals and ensure unambiguous typing.

Instead, `pytae` provides two clean, powerful options for range filtering:

### Option 1: `("between", min, max)`
Pass `("between", min, max)` inside a dictionary to map directly to Polars' highly optimized native `.is_between(lower, upper)` method:
```python
df.filter({"body_mass_g": ("between", 3000, 4000)})
```

### Option 2: Multi-condition Operator Tuples `(('op1', val1), ('op2', val2))`
Pass a tuple of clean `(operator, value)` pairs inside a dictionary to apply multiple conditions on the same column without string-mashed syntax:
```python
# Inclusive bounds:
df.filter({"body_mass_g": ((">=", 3000), ("<=", 4000))})

# Exclusive or asymmetric bounds:
df.filter({"body_mass_g": ((">", 3000), ("<", 4500))})
df.filter({"bill_length_mm": ((">", 40), ("<", 45))})
```

### String Expressions with `and`
You can also write ranges naturally in filter strings:
```python
df.filter("body_mass_g >= 3000 and body_mass_g <= 4000")
```"""))

# Cell 21: Option 1 code
cells.append(nbf.v4.new_code_cell("""# Option 1: ("between", min, max) — inclusive range via dictionary
display(
    penguins
    .filter({"body_mass_g": ("between", 3500, 3800)})
    .select('species', 'island', 'body_mass_g')
    .head(5)
)"""))

# Cell 22: Option 2 code - tuple operators
cells.append(nbf.v4.new_code_cell("""# Option 2: Multi-condition operator tuples (('op', val), ...)
# Clean separation of operators and values; perfect for exclusive or asymmetric bounds:
(
    penguins
    .filter({
        "bill_length_mm": ((">", 40), ("<", 45)),
        "body_mass_g": ((">=", 3500), ("<=", 4000)),
    })
    .select('species', 'bill_length_mm', 'body_mass_g')
    .head(5)
)"""))

# Cell 23: Range in string expressions
cells.append(nbf.v4.new_code_cell("""# Standard string expression range using 'and'
(
    penguins
    .filter("body_mass_g >= 3500 and body_mass_g <= 4000 and bill_depth_mm > 18")
    .select('species', 'bill_depth_mm', 'body_mass_g')
    .head(5)
)"""))

# Cell 24: Section 6 Markdown
cells.append(nbf.v4.new_markdown_cell("""## 6. Columns with Spaces & Bracket Notation `[col]`

When column names contain spaces or special punctuation (such as `bill length mm` or `counterparty_class_(irb)`):
- In **string expressions**, wrap the column name in square brackets: `[bill length mm] > 40`
- In **dictionaries**, use the column name directly as the key without any brackets: `{"bill length mm": "> 40"}`"""))

# Cell 25: Setup spaced columns
cells.append(nbf.v4.new_code_cell("""# Create a DataFrame with spaces in column names
penguins_spaces = penguins.rename(columns={
    'bill_length_mm': 'bill length mm',
    'body_mass_g': 'body mass g',
})
print("Columns with spaces:", penguins_spaces.columns.tolist()[:4])"""))

# Cell 26: Spaced columns in strings
cells.append(nbf.v4.new_code_cell("""# Filtering spaced columns using bracket notation in string expressions:
(
    penguins_spaces
    .filter("[bill length mm] > 45 and [body mass g] > 4000")
    .select('species', '[bill length mm]', '[body mass g]')
    .head(5)
)"""))

# Cell 27: Spaced columns in dictionaries
cells.append(nbf.v4.new_code_cell("""# Filtering spaced columns using plain dictionaries (Option 1 & Option 2 supported!):
(
    penguins_spaces
    .filter({
        "bill length mm": (">", 45),
        "body mass g": ("between", 4000, 5000),
    })
    .select('species', '[bill length mm]', '[body mass g]')
    .head(5)
)"""))

# Cell 28: Section 7 Markdown
cells.append(nbf.v4.new_markdown_cell("""## 7. String Matching (`startswith`, `endswith`, `contains`, `regex`)

For text/string columns, `pytae` provides high-speed pattern matching inside dictionaries:
- `{"col": ('startswith', prefix)}`: Matches string prefix
- `{"col": ('startswith', [prefix1, prefix2, ...])}`: Matches any of several prefixes
- `{"col": ('endswith', suffix)}` / `{"col": ('endswith', [suffix1, suffix2, ...])}`: Matches suffixes
- `{"col": ('contains', substr)}`: Substring search
- `{"col": ('regex', pattern)}`: Regular expression pattern search"""))

# Cell 29: Prefix and suffix
cells.append(nbf.v4.new_code_cell("""# Prefix and suffix matches via dictionary
(
    penguins
    .filter({
        "species": ('startswith', 'Ad'),
        "island": ('endswith', 'e'),
    })
    .select('species', 'island', 'body_mass_g')
    .head(5)
)"""))

# Cell 30: Multiple prefixes
cells.append(nbf.v4.new_code_cell("""# Multiple prefixes: matches species starting with 'Ad' OR 'Ge'
(
    penguins
    .filter({"species": ('startswith', ['Ad', 'Ge'])})
    .by('species')
    .agg("n = count")
)"""))

# Cell 31: Regex pattern
cells.append(nbf.v4.new_code_cell("""# Regex pattern matching (e.g. repeated 'o')
(
    penguins
    .filter({"species": ('regex', r'oo')})
    .by('species')
    .agg("n = count")
)"""))

# Cell 32: Section 8 Markdown
cells.append(nbf.v4.new_markdown_cell("""## 8. Missing and Null Checks (`is_null()`, `is_not_null()`, `is_nan()`, `is_not_nan()`)

In pure Polars and `pytae`, missing values and non-finite numbers follow strict IEEE 754 and relational semantics using a unified **method-token standard** across both string expressions and dictionaries:

1. **`null` values**: Represent missing / absent data across *any* column type.
   - String expressions: `"sex.is_null()"`, `"sex.is_not_null()"` (or bracketed `"[bill length mm].is_not_null()"`)
   - Dictionary mapping: `{"sex": "is_null()"}`, `{"sex": "is_not_null()"}`
   - **Strict Parentheses Required**: In dictionaries, parentheses `()` are strictly enforced (e.g. `{"sex": "is_null()"}`). Bare words like `{"sex": "is_null"}` and `{"sex": None}` raise an immediate diagnostic error with guidance.
   - SQL-style `"is null"` keywords are disallowed in `filter()` (use `-sql` for full SQL queries).
2. **`NaN` values**: Represent floating-point "Not a Number" arithmetic results on *float* columns (`f32`, `f64`).
   - String expressions: `"score.is_nan()"`, `"score.is_not_nan()"`
   - Dictionary mapping: `{"score": "is_nan()"}`, `{"score": "is_not_nan()"}`
   - In Polars, `null` is distinct from `NaN` (`s.is_null()` does not match `NaN`).

For dataset-wide or multi-column missing value handling, use `df.dropna()` or `df.fillna()`."""))

# Cell 33: Method call is_null / is_not_null
cells.append(nbf.v4.new_code_cell("""# Pure Polars null checks in string expressions (supports bracketed spaced columns):
(
    penguins_spaces
    .filter("[bill length mm].is_not_null() and sex.is_not_null()")
    .select('species', 'island', '[bill length mm]', 'sex')
    .head(5)
)"""))

# Cell 34: One obvious way: string predicate and dict method-tokens
cells.append(nbf.v4.new_code_cell("""# Checking for missing values using the universal method-token standard in expressions and dicts:
print("--- Missing sex using string expression (sex.is_null()) ---")
display(
    penguins
    .filter("sex.is_null()")
    .select('species', 'island', 'body_mass_g', 'sex')
    .head(5)
)

print("\\n--- Missing sex using dictionary mapping ({'sex': 'is_null()'}) ---")
display(
    penguins
    .filter({"sex": "is_null()"})
    .select('species', 'island', 'body_mass_g', 'sex')
    .head(5)
)

print("\\n--- Non-missing sex using dictionary mapping ({'sex': 'is_not_null()'}) ---")
display(
    penguins
    .filter({"sex": "is_not_null()"})
    .select('species', 'island', 'body_mass_g', 'sex')
    .head(5)
)

print("\\n--- Bare word without parentheses raises explicit ValueError (no forgiving) ---")
try:
    penguins.filter({"sex": "is_null"})
except ValueError as err:
    print("Caught expected ValueError:\\n", err)

print("\\n--- Passing None raises explicit ValueError ---")
try:
    penguins.filter({"sex": None})
except ValueError as err:
    print("Caught expected ValueError:\\n", err)"""))

# Cell 34b: Rejection of SQL is null
cells.append(nbf.v4.new_code_cell("""# SQL-style 'is null' in filter() raises clear guidance to use .is_null():
try:
    penguins.filter("sex is null")
except ValueError as err:
    print("Caught expected ValueError:\\n", err)"""))

# Cell 35: Float NaN checks
cells.append(nbf.v4.new_code_cell("""# Floating-point NaN vs null distinctions on float columns:
df_measurements = pt.DataFrame({
    "sample_id": ["S1", "S2", "S3", "S4"],
    "score": [98.5, float("nan"), None, 76.2],
})

print("--- Original DataFrame ---")
display(df_measurements)

print("\\n--- Floating-point NaNs via expression (score.is_nan()) ---")
display(df_measurements.filter("score.is_nan()"))

print("\\n--- Floating-point NaNs via dictionary ({'score': 'is_nan()'}) ---")
display(df_measurements.filter({"score": "is_nan()"}))

print("\\n--- Non-NaN float measurements via dictionary ({'score': 'is_not_nan()'}) ---")
display(df_measurements.filter({"score": "is_not_nan()"}))"""))

# Cell 36: Section 9 Markdown
cells.append(nbf.v4.new_markdown_cell("""## 9. Column-to-Column Comparisons

You can compare two DataFrame columns directly against each other (e.g., detecting limit breaches or verifying ID reconciliations) in both Python and CLI using bare column names without any `col()` wrapper:"""))

# Cell 37: Column-to-column code
cells.append(nbf.v4.new_code_cell("""# Comparing two columns directly using bare column names
df_risk = pt.DataFrame({
    "exposure": [120, 250, 80, 410],
    "limit": [100, 200, 150, 400],
    "tranche_id": ["T1", "T2", "T3", "T4"],
    "deal_id": ["T1", "D2", "T3", "D4"],
})

print("--- Breaches (exposure > limit) ---")
display(df_risk.filter("exposure > limit"))

print("\\n--- Reconciled (tranche_id == deal_id) ---")
display(df_risk.filter("tranche_id == deal_id"))"""))

# Cell 38: Section 10 Markdown
cells.append(nbf.v4.new_markdown_cell("""## 10. External Variable Injection (`@var` and `col(@var)`)

You can inject external local variables into filter expressions:
- `@var`: Injects a scalar threshold or comparison literal
- `col(@var)`: Injects a dynamic column name from a Python variable"""))

# Cell 39: External variables code
cells.append(nbf.v4.new_code_cell("""# Inject scalar threshold and dynamic column target
threshold = 100
target_col = "deal_id"

display(df_risk.filter("exposure > @threshold and tranche_id == col(@target_col)"))"""))

# Cell 40: Section 11 Markdown
cells.append(nbf.v4.new_markdown_cell("""## 11. Strict Error Handling & Diagnostic Feedback

`pytae` is intentionally designed with helpful, unambiguous error messages that guide you to the right syntax rather than silently failing or doing unexpected things."""))

# Cell 41: Kwargs rejected error
cells.append(nbf.v4.new_code_cell("""# 1. Keyword arguments are strictly rejected (forces '==' and prevents '=' confusion)
try:
    penguins.filter(species="Gentoo")
except TypeError as err:
    print("Caught expected TypeError:\\n", err)"""))

# Cell 42: Single = error
cells.append(nbf.v4.new_code_cell("""# 2. Single '=' in strings is strictly disallowed (reserved for mutate)
try:
    penguins.filter("species = 'Gentoo'")
except ValueError as err:
    print("Caught expected ValueError:\\n", err)"""))

# Cell 43: Comma as boolean operator error
cells.append(nbf.v4.new_code_cell("""# 3. Comma ',' is disallowed as a boolean operator (use 'and')
try:
    penguins.filter("species == 'Gentoo', body_mass_g > 5000")
except ValueError as err:
    print("Caught expected ValueError:\\n", err)"""))

# Cell 44: Bitwise & and | error
cells.append(nbf.v4.new_code_cell("""# 4. Bitwise '&' and '|' are disallowed (use 'and' / 'or')
try:
    penguins.filter("species == 'Gentoo' & body_mass_g > 5000")
except ValueError as err:
    print("Caught expected ValueError:\\n", err)"""))

# Cell 45: Legacy interval error
cells.append(nbf.v4.new_code_cell("""# 5. Legacy interval strings '[3000, 4000]' are disallowed
try:
    penguins.filter("body_mass_g = [3000, 4000]")
except ValueError as err:
    print("Caught expected ValueError:\\n", err)"""))

# Cell 46: Type mismatch on string column
cells.append(nbf.v4.new_code_cell("""# 6. String column type safety: unquoted int against string column raises TypeError
df_str = pt.DataFrame({"id": ["1", "9", "10"], "val": [100, 200, 300]})

try:
    df_str.filter("id == 9")
except TypeError as err:
    print("Caught expected TypeError:\\n", err)"""))

# Cell 47: Typo suggestion on unknown column
cells.append(nbf.v4.new_code_cell("""# 7. Typo suggestion on misspelled column names
try:
    penguins.filter("speceis == 'Adelie'")
except (KeyError, Exception) as err:
    print("Caught expected error:\\n", err)"""))

# Cell 48: Section 12 Markdown
cells.append(nbf.v4.new_markdown_cell("""## 12. Real-World Analytical Pipelines

Filter works seamlessly as the entry point or intermediate step in pytae pipelines combining filtering, grouping, aggregation, reshaping, and sorting."""))

# Cell 49: Pipeline with tips
cells.append(nbf.v4.new_code_cell("""# Tips dataset: weekend dinner parties of 2+ spending > $15
(
    tips
    .filter("day in ['Sat', 'Sun'] and time == 'Dinner' and size >= 2 and total_bill > 15")
    .by('smoker')
    .agg("mean_tip = tip:mean, mean_bill = total_bill:mean, total_diners = size:sum, n_tables = count")
    .arrange("mean_tip desc")
)"""))

# Cell 50: Pipeline with titanic
cells.append(nbf.v4.new_code_cell("""# Titanic dataset: survival rate of passengers in 1st/2nd class by sex
(
    titanic
    .filter("pclass in [1, 2] and age.is_not_null()")
    .filter({"age": ("between", 18, 60)})
    .by('pclass', 'sex')
    .agg("survival_rate = survived:mean, n_passengers = count")
    .arrange("pclass, sex")
)"""))

nb.cells = cells

out_path = Path("docs/detailed_docs/library/filter.ipynb")
with open(out_path, "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print(f"Successfully generated {out_path} with {len(cells)} cells.")
