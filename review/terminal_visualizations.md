# Pytae Terminal Visualizations Proposal: `-bar`, `-scatter`, and `-corr`

**Date:** October 2026  
**Status:** Recommended / Design Complete (Ready for Implementation)  
**Related Existing Flags:** `-freq`, `-hist`  
**Target Modules:** `src/pytae/other_utilities.py`, `src/pytae/dataframe.py`, `src/pytae/cli.py`, `src/pytae/cli_run.py`, `src/pytae/cli_help.py`

---

## 1. Executive Summary & Design Philosophy

Pytae excels at fast, low-friction command-line data exploration. While `-freq` (categorical row counts) and `-hist` (continuous numeric binning) provide excellent ASCII visualizations, analytical exploration frequently requires three missing primitives:

1. **`-bar`**: Visualizing the magnitude of *pre-aggregated metric values* (e.g. sums, means, percentages) across categories.
2. **`-scatter`**: Inspecting 2D bivariate relationships, non-linear patterns, clusters, and outliers in a high-resolution in-terminal canvas.
3. **`-corr`**: Inspecting pairwise linear/rank correlations across numeric columns in either a classic matrix or a ranked pair list.

### Core Principles
- **Terminal-First & Dependency-Free**: Pure Python and native Polars logic with 0 extra third-party dependencies (no `matplotlib` or heavy plotting libraries required for terminal views).
- **Unix Composability**: Table-based visualizers (`-bar`, `-freq`, `-hist`, `-corr`) return a standard `pytae.DataFrame`. They inherit `-round`, `-o clip`, `-o csv`, and pipe seamlessly into subsequent verbs (`-filter`, `-arrange`, `-head`).
- **One Obvious Way**: No overlapping column-filtering or wildcard-matching flags inside visualizers; standard composition with `-select` is used.
- **Horizontal Orientation**: No vertical rotation (`rot=90`). Monospace terminals have unlimited vertical scrolling and fixed horizontal width; horizontal bars allow arbitrary category name lengths and preserve tabular structure.

---

## 2. Feature 1: `-bar` (Metric Magnitude Visualizer)

### Problem Statement
Currently, running `pytae penguins.parquet -by island -agg avg_mass=body_mass_g:mean` yields an aggregated table, but there is no way to render ASCII bars for those computed averages. `-freq` cannot be used because it only counts raw rows (`pl.len()`).

### Specification & Behavior
- **Bare `-bar` on 2 Columns**:
  If the incoming pipeline table has exactly two columns (1 numeric + 1 non-numeric), bare `-bar` auto-detects the numeric column as the value and the non-numeric column as the category.
  ```bash
  pytae penguins.parquet -by island -agg avg_mass=body_mass_g:mean -bar
  ```
- **Single Column Target (`-bar col`)**:
  Preserves all existing metadata columns intact and appends the `Bar` column to the far right.
  ```bash
  pytae penguins.parquet -by species,island -agg avg_mass=body_mass_g:mean -bar avg_mass
  ```
  *Output:*
  ```
  ┌───────────┬───────────┬──────────┬──────────────────────┐
  │ species   │ island    │ avg_mass │ Bar                  │
  ├───────────┼───────────┼──────────┼──────────────────────┤
  │ Adelie    │ Biscoe    │ 3709.66  │ ██████████████▌      │
  │ Adelie    │ Dream     │ 3688.39  │ ██████████████▍      │
  │ Adelie    │ Torgersen │ 3706.37  │ ██████████████▌      │
  │ Chinstrap │ Dream     │ 3733.09  │ ██████████████▋      │
  │ Gentoo    │ Biscoe    │ 5076.02  │ ████████████████████ │
  └───────────┴───────────┴──────────┴──────────────────────┘
    Rows: 5 | Mean: 3,982.7 | Min: 3,688.4 | Max: 5,076.0
  ```
- **Explicit Pair (`-bar "cat:val"`)**:
  Explicitly targets category and value columns (useful when multiple numeric columns exist).
  ```bash
  pytae data.csv -bar "island:avg_mass"
  ```
- **Preserving Row Order**:
  Unlike `-freq` (which always sorts descending by count), `-bar` **preserves the input row order**, allowing explicit ordering with `-arrange` or preserving chronological time-series order.
- **Column Header**: Named **`Bar`** (crisp, accurate, avoids confusing metric values with a statistical "Distribution").
- **Text Beside Bar**: Option C (clean bars by default; optional percentage with `pct=true`).
- **Optional Limits (`limit=(min, max)`)**:
  - Default: scales from `0` to $\max(\text{values})$ for non-negative data (prevents misleading zero-offset proportions); scales from $\min$ to $\max$ if negative values exist.
  - Custom limit: `-bar "avg_mass,limit=(3000, 5500)"` zooms in or sets fixed bounds.
- **Configurable Width**: `width=N` (default: 20 chars).

---

## 3. Feature 2: `-scatter` (2D In-Terminal Spatial Canvas)

### Problem Statement
Detecting non-linear trends, clustering, and bivariate relationships currently requires launching a heavy GUI/browser window with `-plot`. In-terminal scatter plotting gives instant EDA feedback in milliseconds.

### Specification & Behavior
- **Rendering Engine**: Unicode Braille matrix (`U+2800`–`U+28FF`).
  - Each character cell contains a 2-column × 4-row grid of sub-pixels.
  - A compact 50×15 terminal character box provides an effective **100 × 60 subpixel canvas**.
- **Bare `-scatter`**:
  If the dataset or incoming view contains exactly 2 numeric columns, bare `pytae data.parquet -scatter` auto-selects them (`x=col1, y=col2`).
- **Explicit Columns**:
  ```bash
  pytae penguins.parquet -scatter "bill_length_mm:bill_depth_mm"
  ```
- **Mockup Output**:
  ```
   bill_depth_mm
    21.5 ┤            ⢀⣀⡀
    19.5 ┤     ⢀⠔⠁ ⡠⠂  ⠱⡀   ⡠⠂
    17.5 ┤    ⠐⠁   ⠒   ⠐⠒⠁    ⢀⠜
    15.5 ┤                ⠠⠤⡀ ⢀⠎
    13.5 ┤                 ⠐⠁⠒⠁
         ┼─────────────────────────────────
        30.0     40.0     50.0     60.0  bill_length_mm

    Points: 342 (2 nulls excluded) | Corr (r): -0.235
  ```
- **Footer Statistics**:
  - Shows total valid points and excluded null count.
  - Calculates and displays Pearson correlation coefficient $r$ on the fly.
- **Options**:
  - `width=N, height=N` (defaults: `50` × `15`, fits standard 80-column terminals without wrapping).
  - `limit_x=(min, max), limit_y=(min, max)` for zooming into specific intervals.
- **Pipeline Role**: Visual view. When combined with `-o clip`, copies the formatted ASCII/Unicode plot text.

---

## 4. Feature 3: `-corr` (Pairwise Correlation & Feature Screening)

### Problem Statement
Exploring correlations between features is a foundational step in tabular analysis. Polars' built-in `df.corr()` delegates to `numpy.corrcoef` without pairwise null handling, producing `NaN` whenever missing values exist, and omits row labels.

### Specification & Behavior
- **Numeric Auto-Selection**: Evaluates all numeric columns (floats, ints); ignores strings, dates, and booleans.
- **Pairwise Null Handling**: Calculates pairwise correlations (`pl.corr(col_a, col_b)`) dropping nulls per pair, ensuring robust results without `NaN` blowout.
- **No Wildcards / Clean Composability**: Column selection is delegated to `-select`:
  ```bash
  pytae penguins.parquet -select "starts_with=bill_,body_mass_g" -corr
  ```

### Two Deterministic Output Modes

#### Mode A: The Matrix View (Default)
Always outputs the symmetric $N \times N$ correlation matrix with row labels.
```bash
pytae penguins.parquet -corr
```
```
┌─────────────┬─────────────┬────────────┬─────────────┬───────────┐
│ Column      │ bill_length │ bill_depth │ flipper_len │ body_mass │
├─────────────┼─────────────┼────────────┼─────────────┼───────────┤
│ bill_length │   1.00      │  -0.23     │    0.66     │   0.60    │
│ bill_depth  │  -0.23      │   1.00     │   -0.58     │  -0.47    │
│ flipper_len │   0.66      │  -0.58     │    1.00     │   0.87    │
│ body_mass   │   0.60      │  -0.47     │    0.87     │   1.00    │
└─────────────┴─────────────┴────────────┴─────────────┴───────────┘
```

#### Mode B: The Ranked Pairs View (`-corr pairs`)
Available for *any* number of columns (including small tables with < 6 columns). Unnests the matrix into unique pairs sorted by $|r|$ descending, complete with visual strength bars.
```bash
pytae penguins.parquet -corr pairs
```
```
┌───────────────────┬───────────────────┬──────────┬────────────────────────┐
│ Column A          │ Column B          │ Corr (r) │ Strength               │
├───────────────────┼───────────────────┼──────────┼────────────────────────┤
│ flipper_length_mm │ body_mass_g       │  +0.87   │ █████████ Very Strong  │
│ bill_length_mm    │ flipper_length_mm │  +0.66   │ ███████   Strong       │
│ bill_length_mm    │ body_mass_g       │  +0.60   │ ██████    Moderate     │
│ bill_depth_mm     │ flipper_length_mm │  -0.58   │ ▒▒▒▒▒     Moderate (-) │
│ bill_depth_mm     │ body_mass_g       │  -0.47   │ ▒▒▒▒      Moderate (-) │
│ bill_length_mm    │ bill_depth_mm     │  -0.23   │ ░░        Weak (-)     │
└───────────────────┴───────────────────┴──────────┴────────────────────────┘
```

#### Single Target Screening (`target=col`)
Screens one target variable against all other numeric features:
```bash
pytae penguins.parquet -corr "target=body_mass_g"
```
```
┌───────────────────┬──────────┬──────────────────────┐
│ Feature           │ Corr (r) │ Bar                  │
├───────────────────┼──────────┼──────────────────────┤
│ flipper_length_mm │  +0.87   │ █████████████████▎   │
│ bill_length_mm    │  +0.60   │ ████████████         │
│ bill_depth_mm     │  -0.47   │ ▒▒▒▒▒▒▒▒▒            │
└───────────────────┴──────────┴──────────────────────┘
```
- **Supported Methods**: `method=pearson` (default) and `method=spearman`.

---

## 5. Unified Standardization Across All CLI Visualizers

All four terminal visualizers (`-freq`, `-hist`, `-bar`, `-scatter`) follow a unified pattern for dimensions and summary footers:

| Flag | Focus | Default Width | Key Options | Footer Summary Statistics | Output Type |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **`-freq`** | Categorical counts | `20` | `width=N`, `dropna=bool` | `Total: N \| Unique: N \| Nulls: N` | `DataFrame` |
| **`-hist`** | Continuous bins | `20` | `width=N`, `bins=N` | `Count: N \| Mean: μ \| Std: σ \| Min: a \| Max: b` | `DataFrame` |
| **`-bar`** | Metric values | `20` | `width=N`, `limit=(min,max)`, `pct=bool` | `Rows: N \| Mean: μ \| Min: a \| Max: b` | `DataFrame` |
| **`-scatter`** | 2D $(x, y)$ grid | `50` | `width=N`, `height=N`, `limit_x=...` | `Points: N (nulls) \| Corr (r): Pearson r` | Visual View |
| **`-corr`** | Pairwise relationships | Matrix / 20 | `pairs`, `target=col`, `method=...` | `Features: N \| Pairs: N` | `DataFrame` |

---

## 6. Implementation Checklist (For Later)

- [ ] **`src/pytae/other_utilities.py`**:
  - Implement `bar(df, cat=None, val=None, limit=None, pct=False, width=20)`
  - Implement `scatter(df, x=None, y=None, width=50, height=15, limit_x=None, limit_y=None)`
  - Implement `corr(df, target=None, pairs=False, method="pearson")`
  - Enhance `freq()` and `hist()` to accept `width` and append summary stats
- [ ] **`src/pytae/dataframe.py` & `src/pytae/__init__.py`**:
  - Expose `df.pt.bar()`, `df.pt.scatter()`, `df.pt.corr()` and top-level `pt.bar()`, `pt.scatter()`, `pt.corr()`
- [ ] **`src/pytae/cli.py` & `src/pytae/cli_parsing.py`**:
  - Add `-bar`, `-scatter`, `-corr` arguments to argument parser
  - Add parsing for `limit=(min,max)`, `pairs`, `target=col`, `method=...`
- [ ] **`src/pytae/cli_run.py`**:
  - Hook `-bar`, `-scatter`, `-corr` into the ordered execution loop
- [ ] **`src/pytae/cli_help.py` & Documentation**:
  - Add keywords `bar`, `scatter`, `corr` to `pytae -help`
  - Update quickstarts and CLI guides
- [ ] **Tests (`tests/`)**:
  - Add unit and CLI tests for `-bar`, `-scatter`, `-corr`

