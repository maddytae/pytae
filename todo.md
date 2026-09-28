# Pytae TODO & Future Enhancements

## Planned Deprecations
- [ ] **Deprecate `-crosstab` CLI flag in next release**:
  - **Rationale**: `-crosstab` duplicates existing orthogonal primitives (`-by ... -agg ... -wide ...`), introduces complex multi-key argument parsing (`index=`, `columns=`, `values=`, `aggfunc=`, `margins=`, `normalize=`), and requires specialized MultiIndex output formatting.
  - **Replacement Workflow**: Standardize all 2D cross-tabulation and matrix workflows on `-by`, `-agg`, and `-wide` (e.g. `pytae data.parquet -by 'island,species' -agg 'mass=body_mass_g:sum' -wide 'c=species,v=mass'`), which naturally produce clean, fully populated flat columns.
  - **Codebase Simplification**:
    - Removes dedicated crosstab parsing, key validations, and error handlers in `cli_parsing.py`.
    - Eliminates ~40 lines of specialized execution and formatting code in `cli_run.py`.
    - Removes the sole MultiIndex branch in the CLI pipeline.
    - Streamlines the test suite and documentation.

## Planned CLI Enhancements
- [ ] **Unix STDIN & Pipe Streaming (`-` as file path)**:
  - **Concept**: Allow `pytae` to accept `-` as the input path to read data streams directly from standard input (e.g. `cat data.csv | pytae - -head 5` or `curl ... | pytae - -shape`).
  - **Cross-Platform Support (macOS, Linux, Windows)**:
    - Read via `sys.stdin.buffer` to prevent Windows CRLF newline corruption and binary data mangling.
    - Buffer into `io.BytesIO` so non-seekable pipe streams support random-access Parquet footer reading.
    - Auto-detect formats using magic bytes (e.g. `b"PAR1"` for Parquet, `\x1f\x8b` for Gzip) with fallback to CSV/delimited text. Support optional `-fmt <format>` override.
    - Fully compatible with PowerShell (`Get-Content data.csv | pytae -`), Windows Command Prompt (`type data.csv | pytae -`), and standard Unix pipes.

- [ ] **Terminal In-Line Visualizations (ASCII Histograms & Frequency Bars)**:
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

- [ ] **Zero-Code Plotting Capability (`-plot "..."` in CLI & `.plot` Enhancements)**:
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
  - **Library `.plot` Ergonomics**:
    - Allow one-shot file export via `df.pt.plot(..., save="plot.png")` or direct figure return without requiring explicit `.finalize()`.
    - Support interactive HTML export (`-o chart.html` or `.plot(..., backend="plotly")`).


## Planned Robustness & Bug Fixes
- [ ] **Parquet Export Type Inference for Mixed Object Columns (`-o parquet`)**:
  - **Issue Reported**:
    ```text
    pytae " (Could not convert '0828' with type str: tried to convert to double", 'Conversion failed for column xxx with type object')
    ```
  - **Root Cause**:
    - When exporting data to Parquet via `-o parquet` (or `write_dataframe(df, ...)` in `src/pytae/readers.py`), PyArrow (`pa.Table.from_pandas` / `df.to_parquet`) performs automatic type inference on Pandas `object` dtype columns.
    - If initial values in a column appear numeric (e.g. integers or floats) or if the column contains mixed types (such as accounting/ERP codes like `p_center`, cost centers, or postal codes with leading zeros like `'0828'`), PyArrow infers `double` and subsequently raises `ArrowInvalid` upon encountering a string value.
  - **Planned Resolution**:
    - **Automatic Fallback / String Coercion**: In `_write_parquet` (`src/pytae/readers.py`), intercept `pyarrow.lib.ArrowInvalid` when conversion fails on `object` columns, identify the failing column(s), coerce them cleanly to string (`df[col] = df[col].astype(str)` or PyArrow `pa.string()`), and retry the write.
    - **Pre-Sanitization of Mixed Object Columns**: Alternatively inspect `object` columns containing mixed types prior to calling `to_parquet` / `from_pandas`, preventing pipeline crashes.
    - **Helpful Diagnostic Warning**: Emit a clear, non-fatal notification when auto-coercing mixed object columns so users are informed of the serialization fallback.

