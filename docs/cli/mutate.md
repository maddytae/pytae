# CLI Feature Guide: Mutating & Computing Columns

Compute new columns or overwrite existing columns with mathematical formulas, ratios, boolean indicators, and Pandas expressions using `-mutate`.

---

## Contents

- [Overview & Rules](#overview--rules)
- [Basic Arithmetic & Unit Conversion](#basic-arithmetic--unit-conversion)
- [Defining Multiple Columns](#defining-multiple-columns)
- [Boolean Indicators & Flags](#boolean-indicators--flags)
- [Handling Column Names With Spaces](#handling-column-names-with-spaces)
- [Loading Specs From a File (`@specs.txt`)](#loading-specs-from-a-file-specstxt)
- [Quoting Syntax Rules](#quoting-syntax-rules)

---

## Overview & Rules

The `-mutate` flag evaluates mathematical and logical expressions using Pandas' evaluation engine.

Syntax:
```bash
pytae data.parquet -mutate "new_col = expression"
```

Key Rules:
1. Column names inside the expression must remain **unquoted** so they resolve as variables: `mass_kg = body_mass_g / 1000`.
2. Wrap column names containing spaces in brackets: `[bmi] = [body mass g] / ([bill length mm] ** 2)`.
3. Separate multiple new column definitions with commas: `"col1 = a + b, col2 = a * 2"`.

---

## Basic Arithmetic & Unit Conversion

Convert penguin body mass from grams to kilograms:

```bash
pytae penguins.parquet \
  -mutate "mass_kg = body_mass_g / 1000" \
  -select "species,body_mass_g,mass_kg" \
  -head 3
```

**Output:**
```text
species  body_mass_g  mass_kg
 Adelie       3750.0     3.75
 Adelie       3800.0     3.80
 Adelie       3250.0     3.25
```

---

## Defining Multiple Columns

Define multiple computed fields in a single `-mutate` invocation:

```bash
pytae penguins.parquet \
  -mutate "mass_kg = body_mass_g / 1000, bill_ratio = bill_length_mm / bill_depth_mm" \
  -select "species,mass_kg,bill_ratio" \
  -round 2 \
  -head 3
```

**Output:**
```text
species  mass_kg  bill_ratio
 Adelie     3.75        2.09
 Adelie     3.80        2.27
 Adelie     3.25        2.24
```

---

## Boolean Indicators & Flags

Create binary flag columns by evaluating boolean comparisons:

```bash
pytae penguins.parquet \
  -mutate "is_heavy = body_mass_g > 4000" \
  -select "species,body_mass_g,is_heavy" \
  -head 3
```

**Output:**
```text
species  body_mass_g  is_heavy
 Adelie       3750.0     False
 Adelie       3800.0     False
 Adelie       3250.0     False
```

---

## Handling Column Names With Spaces

If column names have spaces or hyphens, wrap them in square brackets:

```bash
pytae dataset.csv -mutate "[total weight] = [body mass g] + [extra weight]"
```

---

## Loading Specs From a File (`@specs.txt`)

For complex pipelines with many engineered features, store expressions in an external text file:

```text
# features.txt
mass_kg = body_mass_g / 1000
bill_ratio = bill_length_mm / bill_depth_mm
flipper_to_mass = flipper_length_mm / mass_kg
```

Run via:
```bash
pytae penguins.parquet -mutate @features.txt -head 5
```

---

## Quoting Syntax Rules

In shell environments:
- Enclose the entire argument in double quotes: `-mutate "..."`.
- Inside the expression, use single quotes `'...'` only for string literals.
- Do NOT quote column names:
  - Correct: `mass_kg = body_mass_g / 1000`
  - Incorrect: `mass_kg = 'body_mass_g' / 1000`
