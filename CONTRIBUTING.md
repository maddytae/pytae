# Contributing

```bash
pip install -e ".[dev,notebooks]"
ruff check src tests                          # lint (also runs in CI)
pytest                                        # unit tests
python scripts/run_notebooks.py               # run the notebook check manually
```

Notebooks are intentionally not part of the `pytest` suite (they're slower and exercise plotting/IO end-to-end). They're not run on every commit either — CI's `notebooks` job runs them automatically, but only on a tag push (i.e. right before a release publishes); run `python scripts/run_notebooks.py` yourself if you want to check sooner.
