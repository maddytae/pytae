# Pytae TODO & Future Enhancements

## CLI & Output Formatting
- [ ] **Flatten `-crosstab` terminal stdout by default via `safe_reset_index()`**:
  - **Context**: When `-crosstab` is the final terminal operation, it currently prints with `index=True`, preserving Pandas' default hierarchical MultiIndex console formatting. This suppresses repeated row labels (e.g. leaving lower rows under `sex` blank).
  - **Proposal**: Render `safe_reset_index(result)` on terminal stdout directly (matching downstream steps), so that:
    1. Every row has fully populated, explicit category labels (e.g. `Female`, `Female`, `Male`, `Male`).
    2. Terminal stdout matches downstream chained pipeline steps (`-head`, `-select`, `-sort_by`) and file exports (`-o`), eliminating display divergence between terminal and chained output.
