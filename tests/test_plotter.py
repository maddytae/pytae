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


def test_scatter_groups_by_category_with_labels():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "cat": ["x", "y"]})
    plotter = Plotter().data(df).plot(kind="scatter", x="a", y="b", by="cat")
    handles, labels = plotter.ax.get_legend_handles_labels()
    assert set(labels) == {"x", "y"}


def test_hist_warns_on_unsupported_aggfunc_kwarg():
    df = pd.DataFrame({"a": [1, 2, 3]})
    with pytest.warns(UserWarning, match="not supported for hist plot"):
        Plotter().data(df).plot(kind="hist", column="a", aggfunc="mean")


def test_supported_kwargs_lists_unsupported_and_controls():
    info = Plotter.supported_kwargs("scatter")
    assert set(info["unsupported"]) == {"aggfunc", "dropna"}
    assert "on" in info["pytae_controls"]
    assert "palette" in info["pytae_controls"]


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


def test_plotter_init_with_dataframe():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    p1 = Plotter(df)
    assert p1.df is df
    assert "A" in p1.axd

    p2 = Plotter(df, mosaic="AB")
    assert p2.df is df
    assert "B" in p2.axd


def test_df_pt_plot_accessor():
    import pytae  # noqa: F401 registers df.pt
    df = pd.DataFrame({"x": ["a", "b", "c"], "y": [10, 20, 30]})
    p = df.pt.plot(kind="bar", x="x", y="y", aggfunc="mean").finalize()
    assert isinstance(p, Plotter)
    assert p.ax is not None


def test_box_plot_distribution_not_aggregated():
    df = pd.DataFrame({
        "group": ["A", "A", "A", "B", "B", "B"],
        "val": [1, 2, 9, 10, 11, 20],
    })
    p = Plotter(df).plot(kind="box", x="group", y="val")
    box_data = p.get_data("A")
    assert set(box_data.columns) == {"A", "B"}
    assert len(box_data["A"].dropna()) == 3
    assert len(box_data["B"].dropna()) == 3


def test_kde_hist_accepts_x_as_column_alias():
    df = pd.DataFrame({"val": [1.0, 2.0, 3.0, 4.0, 5.0]})
    # hist with x= instead of column=
    p_hist = Plotter(df).plot(kind="hist", x="val")
    assert p_hist.ax is not None

    # kde with x= instead of column=
    p_kde = Plotter(df).plot(kind="kde", x="val")
    assert p_kde.ax is not None


def test_palette_and_axis_labels():
    df = pd.DataFrame({"cat": ["x", "y"], "v1": [1, 2], "v2": [3, 4]})
    p = Plotter(df).plot(kind="bar", x="cat", y="v1", palette="tab10", xlabel="Category", ylabel="Value")
    assert p.ax.get_xlabel() == "Category"
    assert p.ax.get_ylabel() == "Value"


def test_heatmap_rendering():
    df = pd.DataFrame({"x": ["A", "A", "B", "B"], "y": ["C", "D", "C", "D"], "v": [1, 2, 3, 4]})
    p = Plotter(df).plot(kind="heatmap", x="x", y="v", by="y", aggfunc="mean", annot=True)
    assert p.ax is not None
    table = p.get_data("A")
    assert table.shape == (2, 2)


def test_repr_png_returns_bytes():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    p = Plotter(df).plot(kind="scatter", x="a", y="b").finalize()
    png_bytes = p._repr_png_()
    assert isinstance(png_bytes, bytes)
    assert png_bytes.startswith(b"\x89PNG")


def test_facet_sharex_sharey():
    df = pd.DataFrame({"group": ["g1", "g2"], "x": [1, 2], "y": [3, 4]})
    p = Plotter.facet(df, by="group", x="x", y="y", kind="line", sharex=True, sharey=True)
    assert len(p.axd) == 2


def test_pt_plot_top_level_function():
    import pytae as pt
    df = pd.DataFrame({"day": ["Thur", "Fri"], "bill": [10, 20]})
    p = pt.plot(df, kind="bar", x="day", y="bill", aggfunc="mean").finalize()
    assert isinstance(p, Plotter)
    assert p.ax is not None


def test_plotter_nrows_ncols_without_mosaic():
    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    p = Plotter(df, nrows=1, ncols=2)
    assert set(p.axd.keys()) == {"A", "B"}
    p.plot(on="A", kind="scatter", x="x", y="y")
    p.plot(on="B", kind="line", x="x", y="y")
    p.finalize()
    assert len(p.axd) == 2


def test_scatter_continuous_c_preserves_numeric_ticks():
    df = pd.DataFrame({
        "x": list(range(50)),
        "y": list(range(50)),
        "val": [float(i * 1.5) for i in range(50)],
    })
    p = Plotter(df).plot(kind="scatter", x="x", y="y", c="val", cmap="viridis").finalize()
    # Colorbar axis should have normal small number of ticks, not 50 category ticks
    cb_axes = [ax for ax in p.fig.axes if ax != p.axd["A"]]
    assert len(cb_axes) == 1
    assert len(cb_axes[0].get_yticks()) < 15


def test_pt_finalize_function_explicit_and_implicit():
    import pytae as pt
    df = pd.DataFrame({"day": ["Thur", "Fri"], "bill": [10, 20]})

    # 1. Explicit plotter passed
    p1 = pt.plot(df, kind="bar", x="day", y="bill", aggfunc="mean")
    res1 = pt.finalize(p1)
    assert res1 is p1
    assert not p1.ax.spines["top"].get_visible()

    # 2. Implicit active plotter (zero args)
    p2 = pt.plot(df, kind="bar", x="day", y="bill", aggfunc="mean")
    res2 = pt.finalize()
    assert res2 is p2
    assert not p2.ax.spines["top"].get_visible()

    # 3. Type error when invalid object passed
    with pytest.raises(TypeError, match="Expected a Plotter instance"):
        pt.finalize("not a plotter")

    # 4. Error when no active plotter exists
    Plotter._last_active = None
    with pytest.raises(ValueError, match="No active pytae Plotter"):
        pt.finalize()


def test_plotter_pt_namespace_chaining():
    import pytae as pt
    df = pd.DataFrame({"day": ["Thur", "Fri"], "bill": [10, 20]})

    # Fluent .pt namespace throughout the entire pipeline
    p = df.pt.plot(kind="bar", x="day", y="bill", aggfunc="mean").pt.finalize()
    assert isinstance(p, pt.Plotter)
    assert not p.ax.spines["top"].get_visible()


def test_control_kwargs_secondary_y_and_print_clip(capsys):
    import pytae as pt
    df = pd.DataFrame({"day": ["Thur", "Fri"], "bill": [10, 20], "tip": [2, 4]})

    # secondary_y=True should automatically route to A^
    p = (
        pt.Plotter(df, figsize=(8, 4))
        .plot(on="A", kind="bar", x="day", y="bill", aggfunc="mean")
        .plot(kind="line", x="day", y="tip", aggfunc="mean", secondary_y=True, print_data=True, clip_data=True)
        .finalize()
    )
    assert "A^" in p.axd
    captured = capsys.readouterr()
    assert "tip" in captured.out


def test_auto_facet_by_and_ncols():
    import pytae as pt
    df = pd.DataFrame({
        "grp": ["g1", "g1", "g2", "g2", "g3", "g3"],
        "x": [1, 2, 1, 2, 1, 2],
        "y": [10, 20, 15, 25, 12, 22],
    })

    # 1. Top-level pt.plot with by and ncols auto-facets
    p1 = pt.plot(df, by="grp", ncols=3, kind="scatter", x="x", y="y", title="Facet Title").finalize()
    assert set(p1.axd.keys()) == {"g1", "g2", "g3"}
    assert p1.fig._suptitle.get_text() == "Facet Title"

    # 2. DataFrame accessor df.pt.plot with by and ncols auto-facets
    p2 = df.pt.plot(by="grp", ncols=3, kind="scatter", x="x", y="y").pt.finalize()
    assert set(p2.axd.keys()) == {"g1", "g2", "g3"}

    # 3. Class constructor Plotter(df, by=..., ncols=...) auto-facets
    p3 = pt.Plotter(df, by="grp", ncols=3, kind="scatter", x="x", y="y").finalize()
    assert set(p3.axd.keys()) == {"g1", "g2", "g3"}

    # 4. col="grp" alias auto-facets
    p4 = pt.plot(df, col="grp", ncols=3, kind="scatter", x="x", y="y").finalize()
    assert set(p4.axd.keys()) == {"g1", "g2", "g3"}

    # 5. Non-faceted subplots (no by) still creates standard panels A, B
    p5 = pt.Plotter(df, nrows=1, ncols=2)
    assert set(p5.axd.keys()) == {"A", "B"}








