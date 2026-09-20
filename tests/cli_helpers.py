"""Shared fixtures for CLI tests."""
from __future__ import annotations

import pandas as pd


def _write_csv(tmp_path, df: pd.DataFrame) -> str:
    path = tmp_path / "data.csv"
    df.to_csv(path, index=False)
    return str(path)


def _penguins_frame():
    return pd.DataFrame({
        "species": ["Adelie", "Adelie", "Adelie", "Chinstrap", "Chinstrap", "Gentoo", "Gentoo", "Gentoo"],
        "island": ["Biscoe", "Dream", "Dream", "Dream", "Dream", "Biscoe", "Biscoe", "Biscoe"],
        "sex": ["Male", "Female", "Male", "Male", "Female", "Male", "Female", "Male"],
        "body_mass_g": [3750, 3800, 4000, 3700, 3400, 5700, 4500, 5600],
    })


def _replace_frame():
    return pd.DataFrame({
        "col a": ["a magician", "not a magician exactly", "analphabet"],
        "colb": ["alpha", "alpha team", "x"],
    })


def _messy_headers_frame():
    return pd.DataFrame({
        "  Col A  ": [1],
        "col   b": [2],
        "Col A": [3],
        "100% Match!": [4],
    })


def _write_two_csvs(tmp_path):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    pd.DataFrame({"col a": [1, 2, 3], "val_l": ["a", "b", "c"]}).to_csv(left, index=False)
    pd.DataFrame({"cola": [1, 2, 4], "val_r": ["x", "y", "z"]}).to_csv(right, index=False)
    return str(left), str(right)


def _write_three_id_csvs(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    c = tmp_path / "c.csv"
    pd.DataFrame({"id": [1, 2, 3], "x": ["a", "b", "c"]}).to_csv(a, index=False)
    pd.DataFrame({"id": [1, 2, 4], "y": ["p", "q", "r"]}).to_csv(b, index=False)
    pd.DataFrame({"id": [1, 2], "z": ["m", "n"]}).to_csv(c, index=False)
    return str(a), str(b), str(c)
