from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient

NOTEBOOKS_DIR = Path(__file__).resolve().parent.parent / "notebooks"
NOTEBOOK_PATHS = sorted(NOTEBOOKS_DIR.glob("*.ipynb"))


@pytest.mark.parametrize("notebook_path", NOTEBOOK_PATHS, ids=lambda p: p.name)
def test_notebook_runs_without_error(notebook_path, monkeypatch):
    monkeypatch.setenv("MPLBACKEND", "Agg")
    nb = nbformat.read(notebook_path, as_version=4)
    client = NotebookClient(nb, timeout=120, kernel_name="python3", resources={"metadata": {"path": str(NOTEBOOKS_DIR)}})
    client.execute()
