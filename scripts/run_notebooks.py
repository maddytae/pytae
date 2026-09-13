#!/usr/bin/env python
"""Execute every notebook under notebooks/ and fail if any cell raises.

Run manually with: python scripts/run_notebooks.py
Wired up as a pre-commit check via .githooks/pre-commit.
"""
import os
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

NOTEBOOKS_DIR = Path(__file__).resolve().parent.parent / "notebooks"


def main() -> int:
    os.environ.setdefault("MPLBACKEND", "Agg")
    notebook_paths = sorted(NOTEBOOKS_DIR.glob("*.ipynb"))
    if not notebook_paths:
        print(f"no notebooks found under {NOTEBOOKS_DIR}")
        return 0

    failed = []
    for path in notebook_paths:
        print(f"running {path.name} ... ", end="", flush=True)
        nb = nbformat.read(path, as_version=4)
        client = NotebookClient(
            nb, timeout=120, kernel_name="python3",
            resources={"metadata": {"path": str(NOTEBOOKS_DIR)}},
        )
        try:
            client.execute()
        except CellExecutionError as exc:
            print("FAILED")
            failed.append((path.name, str(exc)))
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
