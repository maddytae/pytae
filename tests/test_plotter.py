import os
import sys

import matplotlib

matplotlib.use("Agg")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae.plotting import Plotter


def test_plotter_constructs_default_axis():
    plotter = Plotter()
    assert "A" in plotter.axd
    assert plotter.fig is not None
