import os
import sys

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae.plotting import Plotter


def test_plotter_constructs_default_axis():
    plotter = Plotter()
    assert "A" in plotter.axd
    assert plotter.fig is not None


def test_pie_plot_does_not_overwrite_plotter_df():
    df = pd.DataFrame({"cat": ["a", "a", "b"], "val": [1, 2, 3]})
    plotter = Plotter().data(df)
    plotter.plot(x="cat", y="val", kind="pie", by="cat")
    pd.testing.assert_frame_equal(plotter.df, df)


def test_unknown_mosaic_on_key_raises():
    df = pd.DataFrame({"cat": ["a", "a", "b"], "val": [1, 2, 3]})
    plotter = Plotter(mosaic="AB").data(df)
    with pytest.raises(ValueError, match="Unknown mosaic key"):
        plotter.plot(x="cat", y="val", kind="bar", on="Z")
