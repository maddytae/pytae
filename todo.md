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
