import subprocess
import sys


def test_import_does_not_load_plotting_or_samples():
    code = r"""
import sys
import pytae

assert "pytae.plotting" not in sys.modules
assert "matplotlib" not in sys.modules
assert pytae._cache == {}
assert "penguins" in pytae.sample_data
assert list(pytae.sample_data.keys())
assert pytae._cache == {}

df = pytae.sample("penguins")
assert len(df) > 0
assert pytae.sample_data["penguins"] is df

Plotter = pytae.Plotter
assert "pytae.plotting" in sys.modules
assert Plotter is not None
"""
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
