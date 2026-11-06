# PyTAE Workspace Rules & Settings

These instructions apply persistently to all Antigravity/Gemini interactions within the `pytae` repository.

## 1. Branch Strategy & Git Workflow
- **Default Branch**: Always work on `feature/dev` and ensure changes are checked in, unless explicitly instructed otherwise.
- **Protected `master`**: **NEVER** commit anything directly to `master` unless explicitly told to do so.

## 2. Scope of Changes
- **Code Only**: Focus exclusively on code files (e.g. `src/`, `tests/`, implementation scripts).
- **No Unsolicited Doc Edits**: Do **NOT** update documentation files (such as `docs/`, `readme.md`, `changelog.md`, etc.) unless specifically asked to do so on `feature/dev` or `master`.

## 3. Releases & Publishing
- **Explicit Instruction Required**: **NEVER** publish, release, or bump a new version of `pytae` unless explicitly requested.
- **Prerequisites for Publishing**: Before publishing:
  - Ensure all documentation and references are completely up to date.
  - Follow the release protocol in `.agents/rules/release_protocol.md`:
    - Regenerate references via `python scripts/generate_reference.py`.
    - Ensure `reference/pytae_copilot_reference.txt`, `reference/pytae_copilot_instructions.txt`, and `reference/pytae_docs.db` are up to date.
    - Run the test suite (`uv run --with pytest --with matplotlib --with scipy pytest`) and linter (`uv run --with ruff ruff check src tests scripts`).
