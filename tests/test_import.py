import os
import subprocess
import sys

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))


def test_import_does_not_load_plotting_shape_or_samples():
    code = r"""
import sys
sys.path.insert(0, %r)
import pytae

assert "pytae.plotting" not in sys.modules
assert "pytae.shape" not in sys.modules
assert "matplotlib" not in sys.modules
assert pytae._cache == {}
assert "penguins" in pytae.sample_data
assert list(pytae.sample_data.keys())
assert pytae._cache == {}

df = pytae.sample("penguins")
assert len(df) > 0
assert pytae.sample_data["penguins"] is df

assert "pytae.shape" not in sys.modules
long = pytae.long
assert "pytae.shape" in sys.modules
assert long is not None

Plotter = pytae.Plotter
assert "pytae.plotting" in sys.modules
assert Plotter is not None
""" % _SRC
    subprocess.check_call([sys.executable, "-c", code])


def test_cli_import_does_not_load_shape_or_plotting():
    code = r"""
import sys
sys.path.insert(0, %r)
import pytae.cli

assert "pytae.plotting" not in sys.modules
assert "pytae.shape" not in sys.modules
assert "matplotlib" not in sys.modules
assert hasattr(sys.modules["pandas"].DataFrame, "qry")
assert hasattr(sys.modules["pandas"].DataFrame, "select")
assert hasattr(sys.modules["pandas"].DataFrame, "agg_df")
assert hasattr(sys.modules["pandas"].DataFrame, "group_x")
assert hasattr(sys.modules["pandas"].DataFrame, "handle_missing")
""" % _SRC
    subprocess.check_call([sys.executable, "-c", code])


def test_sample_unknown_dataset():
    import pytae

    try:
        pytae.sample("not_a_real_dataset")
    except KeyError as exc:
        assert "not_a_real_dataset" in str(exc)
        assert "penguins" in str(exc)
    else:
        raise AssertionError("expected KeyError")
