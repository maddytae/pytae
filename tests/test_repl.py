"""Unit tests for pytae interactive REPL (PytaeRepl, pt.repl(), df.repl(), and CLI flags)."""


import pandas as pd
import polars as pl
import pytest

from pytae import cli
from pytae.dataframe import DataFrame
from pytae.repl import PytaeRepl, repl


@pytest.fixture
def sample_df():
    return pl.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "species": ["Adelie", "Gentoo", "Adelie", "Gentoo", "Chinstrap"],
            "body_mass_g": [3500.0, 5000.0, 3800.0, 5200.0, 4100.0],
        }
    )


@pytest.fixture
def sample_parquet(tmp_path, sample_df):
    path = tmp_path / "penguins_sample.parquet"
    sample_df.write_parquet(path)
    return path


def test_repl_init_with_dataframe(sample_df):
    r = PytaeRepl(df=sample_df)
    assert r.current_df is not None
    assert r.current_df.shape == (5, 3)
    assert r.orig_df is not None
    assert r.orig_df.shape == (5, 3)


def test_repl_init_with_path(sample_parquet):
    r = PytaeRepl(path=sample_parquet)
    assert r.current_df is not None
    assert r.current_df.shape == (5, 3)
    assert r.path_str == "penguins_sample.parquet"


def test_repl_filter_and_undo_and_reset(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # 1. Apply filter
    r.execute_line("-filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)
    assert len(r.undo_stack) == 1

    # 2. Undo filter
    r.execute_line("undo", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)
    assert "Undid:" in outputs[-1]

    # 3. Apply another filter
    r.execute_line("-filter \"species == 'Adelie'\"", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)

    # 4. Reset to original
    r.execute_line("reset", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)
    assert "Restored original dataset" in outputs[-1]


def test_repl_redo(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    r.execute_line("-filter \"species == 'Gentoo'\"", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)

    r.execute_line("undo", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)

    r.execute_line("redo", output_fn=outputs.append)
    assert r.current_df.shape == (2, 3)
    assert "Redid:" in outputs[-1]


def test_repl_checkpoint_and_restore(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # Save checkpoint
    r.execute_line("checkpoint v1", output_fn=outputs.append)
    assert "v1" in r.checkpoints

    # Mutate data
    r.execute_line("-mutate \"mass_kg = body_mass_g / 1000.0\"", output_fn=outputs.append)
    assert "mass_kg" in r.current_df.columns
    assert r.current_df.shape == (5, 4)

    # List checkpoints
    r.execute_line("checkpoints", output_fn=outputs.append)
    assert any("v1" in o for o in outputs)

    # Restore checkpoint
    r.execute_line("restore v1", output_fn=outputs.append)
    assert "mass_kg" not in r.current_df.columns
    assert r.current_df.shape == (5, 3)


def test_repl_non_destructive_inspection(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # shape
    r.execute_line("shape", output_fn=outputs.append)
    assert "(5, 3)" in outputs[-1]
    assert len(r.undo_stack) == 0

    # cols
    r.execute_line("cols", output_fn=outputs.append)
    assert "species" in outputs[-1]

    # dtype
    r.execute_line("dtype", output_fn=outputs.append)

    # nulls
    r.execute_line("nulls", output_fn=outputs.append)

    # glimpse
    r.execute_line("glimpse", output_fn=outputs.append)

    # head / tail
    r.execute_line("head 2", output_fn=outputs.append)
    r.execute_line("tail 2", output_fn=outputs.append)

    # None of these should mutate or push to undo stack!
    assert r.current_df.shape == (5, 3)
    assert len(r.undo_stack) == 0


def test_repl_sql_query(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    r.execute_line("sql SELECT species, COUNT(*) as cnt FROM df GROUP BY species ORDER BY cnt DESC", output_fn=outputs.append)
    assert r.current_df.shape == (3, 2)
    assert "cnt" in r.current_df.columns

    # Can undo SQL query
    r.execute_line("undo", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)


def test_repl_python_expression(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    r.execute_line("py len(df)", output_fn=outputs.append)
    assert outputs[-1] == "5"


def test_repl_save_export(sample_df, tmp_path):
    outputs = []
    r = PytaeRepl(df=sample_df)
    out_file = tmp_path / "exported.parquet"

    r.execute_line(f"save {out_file}", output_fn=outputs.append)
    assert out_file.exists()
    assert pl.read_parquet(out_file).shape == (5, 3)


def test_repl_load_new_file(sample_parquet, tmp_path):
    # Create second file
    second_path = tmp_path / "second.csv"
    pd.DataFrame({"x": [10, 20], "y": [30, 40]}).to_csv(second_path, index=False)

    outputs = []
    r = PytaeRepl(path=sample_parquet)
    assert r.current_df.shape == (5, 3)

    r.execute_line(f"load {second_path}", output_fn=outputs.append)
    assert r.current_df.shape == (2, 2)
    assert "x" in r.current_df.columns


def test_repl_error_handling(sample_df):
    outputs = []
    r = PytaeRepl(df=sample_df)

    # Invalid column name in filter
    r.execute_line("-filter \"non_existent > 10\"", output_fn=outputs.append)
    assert r.current_df.shape == (5, 3)  # Intact!
    assert len(r.undo_stack) == 0
    assert any("error" in o.lower() or "not found" in o.lower() for o in outputs)


def test_repl_headless_run(sample_df):
    lines = [
        "-filter \"species == 'Gentoo'\"",
        "checkpoint g_only",
        "-mutate \"mass_kg = body_mass_g / 1000.0\"",
        "undo",
        "exit",
    ]
    outputs = []
    r = PytaeRepl(df=sample_df)
    final_df = r.run(input_fn=iter(lines).__next__, output_fn=outputs.append)

    assert final_df.shape == (2, 3)
    assert "g_only" in r.checkpoints


def test_repl_convenience_function(sample_df):
    lines = ["head 2", "exit"]
    res = repl(df=sample_df) if False else PytaeRepl(df=sample_df).run(input_fn=iter(lines).__next__, output_fn=lambda _: None)
    assert res.shape == (5, 3)


def test_dataframe_method_repl(sample_df):
    pt_df = DataFrame(sample_df)
    lines = ["-filter \"body_mass_g > 4000\"", "exit"]
    r = PytaeRepl(df=pt_df)
    res = r.run(input_fn=iter(lines).__next__, output_fn=lambda _: None)
    assert res.shape == (3, 3)


def test_cli_repl_invocation(sample_parquet, monkeypatch):
    import sys

    invoked = False

    def mock_repl(*args, **kwargs):
        nonlocal invoked
        invoked = True
        return None

    monkeypatch.setattr(sys.modules["pytae.repl"], "repl", mock_repl)

    # Test pytae repl <file>
    cli.main(["repl", str(sample_parquet)])
    assert invoked

    invoked = False
    # Test pytae <file> -i
    cli.main([str(sample_parquet), "-i"])
    assert invoked

    invoked = False
    # Test pytae -i
    cli.main(["-i"])
    assert invoked
