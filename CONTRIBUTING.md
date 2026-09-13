# Contributing

```bash
pip install -e ".[dev,notebooks]"
pytest                                        # unit tests
git config core.hooksPath .githooks           # run notebooks/*.ipynb before each commit
python scripts/run_notebooks.py               # or run the notebook check manually
```

Notebooks are intentionally not part of the `pytest` suite (they're slower and exercise plotting/IO end-to-end); the pre-commit hook is the enforcement point instead.
