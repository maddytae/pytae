import os
import sys

import pytest

# Keep test imports consistent with existing test files.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae


@pytest.fixture
def sample_csv(tmp_path):
    """Factory fixture: write a bundled pytae.sample_data dataset to CSV in tmp_path, return its path."""
    def _write(name: str) -> str:
        path = tmp_path / f"{name}.csv"
        pytae.sample_data[name].to_csv(path, index=False)
        return str(path)
    return _write


@pytest.fixture
def sample_parquet(tmp_path):
    """Factory fixture: write a bundled pytae.sample_data dataset to parquet in tmp_path, return its path."""
    def _write(name: str) -> str:
        path = tmp_path / f"{name}.parquet"
        pytae.sample_data[name].to_parquet(path)
        return str(path)
    return _write
