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
