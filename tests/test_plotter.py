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


def _facet_frame():
    return pd.DataFrame(
        {
            "species": ["Adelie"] * 3 + ["Gentoo"] * 3 + ["Chinstrap"] * 3 + ["Emperor"] * 3 + ["King"] * 3,
            "x": range(15),
            "y": [v * 2 for v in range(15)],
        }
    )


def test_facet_leaves_unfillable_grid_cells_blank():
    # 5 groups in a 2-column grid needs 3 rows (6 cells) -- the leftover cell must
    # stay blank, not become an empty/unused 6th axis.
    plotter = Plotter.facet(_facet_frame(), by="species", ncols=2, x="x", y="y", kind="line")
    assert len(plotter.axd) == 5
    assert len(plotter.fig.axes) == 5


def test_facet_one_axis_per_group_with_own_data():
    df = _facet_frame()
    plotter = Plotter.facet(df, by="species", ncols=2, x="x", y="y", kind="line")
    assert set(plotter.axd.keys()) == {"Adelie", "Gentoo", "Chinstrap", "Emperor", "King"}


def test_facet_sets_axis_titles_by_default():
    plotter = Plotter.facet(_facet_frame(), by="species", ncols=2, x="x", y="y", kind="line")
    assert plotter.axd["Adelie"].get_title() == "Adelie"


def test_facet_titles_can_be_disabled():
    plotter = Plotter.facet(_facet_frame(), by="species", ncols=2, x="x", y="y", kind="line", titles=False)
    assert plotter.axd["Adelie"].get_title() == ""


def test_facet_respects_categorical_order():
    df = _facet_frame()
    df["species"] = pd.Categorical(df["species"], categories=["King", "Emperor", "Gentoo", "Chinstrap", "Adelie"])
    plotter = Plotter.facet(df, by="species", x="x", y="y", kind="line")
    assert list(plotter.axd.keys()) == ["King", "Emperor", "Gentoo", "Chinstrap", "Adelie"]


def test_facet_default_ncols_is_roughly_square():
    plotter = Plotter.facet(_facet_frame(), by="species", x="x", y="y", kind="line")
    assert len(plotter.axd) == 5


def test_facet_no_groups_raises():
    df = _facet_frame()
    with pytest.raises(ValueError, match="no groups found"):
        Plotter.facet(df[0:0], by="species", x="x", y="y", kind="line")


def test_facet_chains_into_finalize():
    plotter = Plotter.facet(_facet_frame(), by="species", ncols=2, x="x", y="y", kind="line")
    assert plotter.finalize() is plotter


def test_facet_restores_full_df_not_just_last_group():
    df = _facet_frame()
    plotter = Plotter.facet(df, by="species", ncols=2, x="x", y="y", kind="line")
    pd.testing.assert_frame_equal(plotter.df, df)


def test_facet_rejects_ncols_less_than_one():
    with pytest.raises(ValueError, match="ncols must be at least 1"):
        Plotter.facet(_facet_frame(), by="species", ncols=0, x="x", y="y", kind="line")


def test_kde_column_without_by_works():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0]})
    plotter = Plotter().data(df).plot(kind="kde", column="a")
    assert plotter.ax is not None


def test_scatter_missing_required_kwargs_raises():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    with pytest.raises(ValueError, match="kind='scatter' needs y="):
        Plotter().data(df).plot(kind="scatter", x="a")


def test_pie_missing_required_kwargs_raises():
    df = pd.DataFrame({"cat": ["a", "b"], "val": [1, 2]})
    with pytest.raises(ValueError, match="kind='pie' needs by="):
        Plotter().data(df).plot(kind="pie", y="val")


def test_hist_missing_required_kwarg_raises():
    df = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(ValueError, match="kind='hist' needs column="):
        Plotter().data(df).plot(kind="hist")


def test_scatter_warns_on_unsupported_by_kwarg():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "cat": ["x", "y"]})
    with pytest.warns(UserWarning, match="'by' argument will be ignored"):
        Plotter().data(df).plot(kind="scatter", x="a", y="b", by="cat")


def test_hist_warns_on_unsupported_aggfunc_kwarg():
    df = pd.DataFrame({"a": [1, 2, 3]})
    with pytest.warns(UserWarning, match="not supported for hist plot"):
        Plotter().data(df).plot(kind="hist", column="a", aggfunc="mean")


def test_supported_kwargs_lists_unsupported_and_controls():
    info = Plotter.supported_kwargs("scatter")
    assert set(info["unsupported"]) == {"aggfunc", "by", "dropna"}
    assert "on" in info["pytae_controls"]


def test_supported_kwargs_kde_alias_matches_density():
    assert Plotter.supported_kwargs("kde") == Plotter.supported_kwargs("density")


def test_save_writes_figure(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    out = tmp_path / "out.png"
    plotter = Plotter().data(df).plot(kind="scatter", x="a", y="b").finalize().save(str(out))
    assert out.exists()
    assert isinstance(plotter, Plotter)


def test_finalize_style_false_skips_spine_and_tick_cleanup():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    plotter = Plotter(mosaic="AB").data(df)
    plotter.plot(kind="scatter", x="a", y="b", on="A")
    plotter.finalize(style=False)
    unused_ax = plotter.axd["B"]
    # style=False means the blank second axis keeps matplotlib's own default
    # ticks/spines instead of pytae hiding them.
    assert unused_ax.spines["bottom"].get_visible()


def test_finalize_style_true_hides_blank_axis_ticks():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    plotter = Plotter(mosaic="AB").data(df)
    plotter.plot(kind="scatter", x="a", y="b", on="A")
    plotter.finalize()
    unused_ax = plotter.axd["B"]
    assert not unused_ax.has_data()
    assert unused_ax.xaxis.get_tick_params()["length"] == 0
