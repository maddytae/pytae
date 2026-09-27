#!/usr/bin/env python
"""Execute every notebook under docs/ and fail if any cell raises.

Run manually with: python scripts/run_notebooks.py
Re-run and save all outputs: python scripts/run_notebooks.py --write
Run automatically in CI's `notebooks` job (.github/workflows/ci.yml), gated to
tag pushes only (i.e. before a release publishes), not on every commit/push.
"""
import argparse
import os
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute notebooks and optionally save outputs.")
    parser.add_argument("--write", "--save", "-w", action="store_true", help="Write executed outputs back to .ipynb files")
    args, _ = parser.parse_known_args()

    if not args.write:
        os.environ.setdefault("MPLBACKEND", "Agg")
    else:
        os.environ.pop("MPLBACKEND", None)

    notebook_paths = sorted(DOCS_DIR.glob("**/*.ipynb"))
    if not notebook_paths:
        print(f"no notebooks found under {DOCS_DIR}")
        return 0

    failed = []
    for path in notebook_paths:
        print(f"running {path.relative_to(DOCS_DIR)} ... ", end="", flush=True)
        nb = nbformat.read(path, as_version=4)
        is_ci = bool(os.environ.get("CI"))
        if is_ci:
            # headless CI runners have no system clipboard; no-op to_clipboard()
            # inside the notebook's own kernel process (this script's process
            # doesn't share memory with it, so patch via an injected cell)
            nb.cells.insert(0, nbformat.v4.new_code_cell(
                "import pandas as pd\n"
                "pd.DataFrame.to_clipboard = lambda self, *a, **k: None"
            ))
        client = NotebookClient(
            nb, timeout=180, kernel_name="python3",
            resources={"metadata": {"path": str(path.parent)}},
        )
        try:
            client.execute()
        except CellExecutionError as exc:
            print("FAILED")
            failed.append((path.name, str(exc)))
        else:
            if is_ci and nb.cells and "pd.DataFrame.to_clipboard" in nb.cells[0].get("source", ""):
                nb.cells.pop(0)
            if args.write:
                nbformat.write(nb, path)
                print("ok (saved)")
            else:
                print("ok")

    if failed:
        print("\nnotebook execution failed:")
        for name, msg in failed:
            print(f"\n=== {name} ===\n{msg}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
