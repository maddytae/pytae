# Pytae TODO & Future Enhancements

## Planned Deprecations
- [x] **Deprecate `-crosstab` CLI flag in next release**:
  - **Rationale**: `-crosstab` duplicates existing orthogonal primitives (`-by ... -agg ... -wide ...`), introduces complex multi-key argument parsing (`index=`, `columns=`, `values=`, `aggfunc=`, `margins=`, `normalize=`), and requires specialized MultiIndex output formatting.
  - **Replacement Workflow**: Standardize all 2D cross-tabulation and matrix workflows on the planned `-pivot "r=..., c=..., a=..."` primitive or `-by`, `-agg`, and `-wide` (which naturally produce clean, fully populated flat columns without MultiIndex overhead).
  - **Status**: Added deprecation warning (`FutureWarning`) and annotated help text in CLI.

## Planned CLI Enhancements
- [x] **Unix STDIN & Pipe Streaming (`-` as file path)**:
  - **Concept**: Allow `pytae` to accept `-` as the input path to read data streams directly from standard input (e.g. `cat data.csv | pytae - -head 5` or `curl ... | pytae - -shape`).
  - **Cross-Platform Support (macOS, Linux, Windows)**:
    - Read via `sys.stdin.buffer` to prevent Windows CRLF newline corruption and binary data mangling.
    - Buffer into memory via `StdinReader` so non-seekable pipe streams support random-access Parquet footer reading.
    - Auto-detect formats using magic bytes (e.g. `b"PAR1"` for Parquet, `\x1f\x8b` for Gzip) with fallback to CSV/delimited text. Support optional `-fmt <format>` override.
    - Fully compatible with PowerShell (`Get-Content data.csv | pytae -`), Windows Command Prompt (`type data.csv | pytae -`), and standard Unix pipes.

- [x] **Terminal In-Line Visualizations (ASCII Histograms & Frequency Bars)**:
  - **Concept**: Fast, lightweight visual data exploration directly inside the terminal console without GUI windows or image files.
  - **Features**:
    - **Categorical Frequency Bars (`-freq COL`)**: Render horizontal Unicode/ASCII frequency bars with counts and percentages:
      ```text
      species    Count  Distribution
      Adelie       152  ████████████████████ (44.2%)
      Gentoo       124  ████████████████     (36.0%)
      Chinstrap     68  █████████            (19.8%)
      ```
    - **Numeric Distribution Histograms (`-hist COL [BINS]`)**: Render binned ASCII histograms showing numeric distributions, spread, and peaks directly in console scrollback.

- [x] **Ergonomic 2D Pivoting (`-pivot "r=..., c=..., v=..., a=..., dropna=..."` and `pt.pivot(...)`)**:
  - **Concept**: Provide a first-class, ultra-intuitive 2D pivot table command and library function mimicking Excel Pivot Tables with automatic index resetting and flat 1D column names.
  - **Key Parameters**:
    - `r` (or `rows`, `index`, `by`): Row dimension(s) (optional; single or multiple columns, e.g. `r=Region` or `r=Region,Store`).
    - `c` (or `cols`, `columns`): Column dimension(s) to spread as headers (optional; single or multiple columns, e.g. `c=Year` or `c=Year,Quarter`).
    - `v` (or `values`, `val`): Value column(s) to aggregate (required; e.g. `v=Sales` or `v=Sales,Profit`).
    - `a` (or `agg`, `aggfunc`): Aggregation function (`sum`, `mean`, `median`, `min`, `max`, `count`, `std`, `n`/`size`; default: `sum`).
    - `dropna`: Control whether missing categories are retained (`default: false` across library and CLI).
    - `fill_value` (or `fill`): Optional fill value for missing grid intersections (e.g. `fill=0`).
  - **Guarantees**:
    - Always returns a clean, rectangular DataFrame with standard `RangeIndex(0, 1, 2, ...)` and 1D column names (MultiIndex tuples flattened with `_`).
    - Subsets DataFrame automatically to only `r`, `c`, and `v`—no `-select` needed beforehand.
    - Zero presentation pollution: no subtotals or grand totals, ensuring full relational downstream chaining.

- [x] **Zero-Code Plotting Capability (`-plot "..."` in CLI & `.plot` Enhancements)**:
  - **Concept**: Connect `pytae`'s visualization engine (`df.pt.plot` / `Plotter`) directly to the command line, fulfilling the project description (*"zero-code CLI for tabular data manipulation and plotting"*), and expand library `.plot` convenience.
  - **CLI Pipeline Plotting (`-plot "..."`)**:
    - **Syntax**: Pass plotting arguments as comma-delimited key-value strings:
      ```bash
      # Filter, group, aggregate, and generate a chart in a single command
      pytae tips.parquet \
        -by day \
        -agg "avg_tip=tip:mean" \
        -plot "kind=bar, x=day, y=avg_tip, title='Average Tip by Day'" \
        -o avg_tips.png

      # Multi-dimensional scatter plot with color hue
      pytae penguins.parquet \
        -qry "sex = ('notna',)" \
        -plot "kind=scatter, x=bill_length_mm, y=body_mass_g, color=species" \
        -o penguins_scatter.svg
      ```
    - **Rendering & Output Modes**:
      - **Headless File Export (`-o <file>.<png|svg|pdf|jpg>`)**: Uses `matplotlib.use('Agg')` for clean background rendering without GUI popup windows; ideal for automated scripts, CI/CD pipelines, and remote SSH environments.
      - **Interactive GUI (`--show`)**: When passed or when `-o` is omitted, opens an interactive window (`plt.show()`) for panning and zooming.
    - **Supported Chart Types**: `scatter`, `line`, `bar`, `hist`, `box`, `violin`, `heatmap`, `count`.
    - **CLI Layout Finalization (`-finalize "..."`)**:
      - **Auto-finalize by default**: The CLI automatically executes `.finalize()` before saving or displaying figures, so single-shot commands look polished with clean spines and `tight_layout` without needing manual flags.
      - **Custom finalization (`-finalize "..."`)**: Optional flag to configure `Plotter.finalize(...)` parameters (e.g. `-finalize "consolidate_legends=True, legend_loc='upper right', style=False"`).
  - **Library `.plot` Ergonomics**:
    - **Retain `.finalize()` as core pipeline method**: Keep `.finalize()` as the indispensable method for multi-panel dashboards, dual-axis charts, and mosaics to polish all axes after composition.
    - **Convenience `save=` parameter**: Allow optional `df.pt.plot(..., save="plot.png")` to auto-call `.finalize()` and save in one step for simple single-panel plots without breaking manual chaining.
    - **Interactive HTML export**: Support `-o chart.html` / `.plot(..., backend="plotly")`.


## Planned Robustness & Bug Fixes
- [x] **Parquet Export Type Inference for Mixed Object Columns (`-o parquet`)**:
  - **Issue Reported**:
    ```text
    pytae " (Could not convert '0828' with type str: tried to convert to double", 'Conversion failed for column xxx with type object')
    ```
  - **Root Cause**:
    - When exporting data to Parquet via `-o parquet` (or `write_dataframe(df, ...)` in `src/pytae/readers.py`), PyArrow (`pa.Table.from_pandas` / `df.to_parquet`) performs automatic type inference on Pandas `object` dtype columns.
    - If initial values in a column appear numeric (e.g. integers or floats) or if the column contains mixed types (such as accounting/ERP codes like `p_center`, cost centers, or postal codes with leading zeros like `'0828'`), PyArrow infers `double` and subsequently raises `ArrowInvalid` upon encountering a string value.
  - **Resolution**:
    - **Automatic Fallback / String Coercion**: In `_write_parquet` (`src/pytae/readers.py`), intercept `pyarrow.lib.ArrowInvalid` when conversion fails on `object` columns, identify the failing column(s), coerce them cleanly to string (`df[col] = df[col].astype(str)` or PyArrow `pa.string()`), and retry the write.
    - **Helpful Diagnostic Warning**: Emits `UserWarning: Column '...' contained mixed object types; coerced to string for Parquet serialization.` informing users of the safe serialization fallback.


