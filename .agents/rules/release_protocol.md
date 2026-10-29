# Release & Publishing Protocol Rule

Whenever the user requests to publish, release, bump the version, or cut a release of `pytae`:

1. **Version Synchronization**:
   - Update `version = "X.Y.Z"` in `pyproject.toml`.
   - Update `__version__ = "X.Y.Z"` in `src/pytae/__init__.py`.
   - Update `"version": "X.Y.Z"` in `extensions/vscode-pytae/package.json`.
   - Run `uv lock` to update `uv.lock`.

2. **Mandatory Reference Regeneration**:
   - **ALWAYS** run `python scripts/generate_reference.py`.
   - Verify that all three reference files are regenerated with the updated release version:
     - `reference/pytae_reference.txt`
     - `reference/pytae_copilot_reference.md`
     - `reference/pytae_copilot_instructions.md`
   - Never finalize a release without staging and committing these three regenerated files.

3. **Changelog Updates**:
   - Add release notes in `changelog.md` and `extensions/vscode-pytae/CHANGELOG.md`.

4. **Testing & Validation**:
   - Run `uv run --with pytest --with matplotlib --with scipy pytest`
   - Run `uv run --with ruff ruff check src tests scripts`

5. **Release Commit & Tagging**:
   - Commit with message: `release: bump version to X.Y.Z ...`
   - Tag with `vX.Y.Z` and `X.Y.Z`.
