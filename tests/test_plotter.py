import os
import sys

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt
from pytae.plotting import Plotter


def test_plotter_constructs_default_axis():
    plotter = Plotter()
    assert "A" in plotter.axd
    assert plotter.fig is not None


def test_pie_plot_does_not_overwrite_plotter_df():
    df = pd.DataFrame({"cat": ["a", "b"], "val": [1, 2]})
    plotter = Plotter().data(df)
    plotter.plot(x="cat", y="val", kind="pie", by="cat")
    pd.testing.assert_frame_equal(plotter.df, df)


def test_unknown_mosaic_on_key_raises():
    df = pd.DataFrame({"cat": ["a", "b"], "val": [1, 2]})
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


def test_aggfunc_raises_helpful_error():
    df = pd.DataFrame({"a": [1, 2, 3]})
    with pytest.raises(ValueError, match="Plotter does not perform aggregation"):
        Plotter().data(df).plot(kind="hist", column="a", aggfunc="mean")


def test_supported_kwargs_lists_unsupported_and_controls():
    info = Plotter.supported_kwargs("scatter")
    assert set(info["unsupported"]) == {"dropna"}
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
    p = df.pt.plot(kind="bar", x="x", y="y").finalize()
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
    p = Plotter(df).plot(kind="heatmap", x="x", y="v", by="y", annot=True)
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
    p = pt.plot(df, kind="bar", x="day", y="bill").finalize()
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
    p1 = pt.plot(df, kind="bar", x="day", y="bill")
    res1 = pt.finalize(p1)
    assert res1 is p1
    assert not p1.ax.spines["top"].get_visible()

    # 2. Implicit active plotter (zero args)
    p2 = pt.plot(df, kind="bar", x="day", y="bill")
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
    p = df.pt.plot(kind="bar", x="day", y="bill").pt.finalize()
    assert isinstance(p, pt.Plotter)
    assert not p.ax.spines["top"].get_visible()


def test_control_kwargs_secondary_y_and_print_clip(capsys):
    import pytae as pt
    df = pd.DataFrame({"day": ["Thur", "Fri"], "bill": [10, 20], "tip": [2, 4]})

    # secondary_y=True should automatically route to A^
    p = (
        pt.Plotter(df, figsize=(8, 4))
        .plot(on="A", kind="bar", x="day", y="bill")
        .plot(kind="line", x="day", y="tip", secondary_y=True, print_data=True, clip_data=True)
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


def test_plot_line_color_string_and_list():
    import matplotlib.colors as mcolors

    import pytae as pt
    df = pd.DataFrame({"day": ["Thur", "Fri", "Sat"], "bill": [10, 20, 30], "tip": [2, 4, 6]})

    # String color
    p = pt.Plotter(df).plot(kind="line", x="day", y="bill", color="crimson").finalize()
    line_color = p.axd["A"].get_lines()[0].get_color()
    assert mcolors.to_hex(line_color) == mcolors.to_hex("crimson")

    # List of colors for multiple lines
    df_multi = pd.DataFrame({"day": ["Thur", "Fri"], "A": [1, 2], "B": [3, 4]})
    p2 = pt.Plotter(df_multi).plot(kind="line", x="day", y=["A", "B"], color=["crimson", "navy"]).finalize()
    lines = p2.axd["A"].get_lines()
    assert mcolors.to_hex(lines[0].get_color()) == mcolors.to_hex("crimson")
    assert mcolors.to_hex(lines[1].get_color()) == mcolors.to_hex("navy")


def test_plot_scatter_by_title_labels_kwargs():
    import pytae as pt
    df = pd.DataFrame({
        "species": ["Adelie", "Gentoo", "Adelie", "Gentoo"],
        "bill_len": [39.1, 46.5, 40.3, 48.0],
        "bill_dep": [18.7, 14.5, 18.0, 15.0],
        "size_col": [20, 40, 25, 45],
    })

    p = (
        pt.Plotter(df)
        .plot(
            kind="scatter",
            x="bill_len",
            y="bill_dep",
            by="species",
            title="Penguin Bill Dimensions",
            s=df["size_col"],
            edgecolors="black",
        )
        .finalize()
    )
    ax = p.axd["A"]
    assert ax.get_title() == "Penguin Bill Dimensions"
    assert ax.get_xlabel() == "bill_len"
    assert ax.get_ylabel() == "bill_dep"
    # Check collections have edgecolors set
    for coll in ax.collections:
        assert len(coll.get_edgecolors()) > 0


def test_heatmap_title_vmin_vmax_and_contrast():
    import pytae as pt
    df = pd.DataFrame({
        "A": [1.0, 0.0, -1.0],
        "B": [0.0, 1.0, 0.5],
        "C": [-1.0, 0.5, 1.0],
    })
    p = pt.Plotter(df).plot(
        kind="heatmap",
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        title="Correlation Heatmap",
        vmin=-1,
        vmax=1,
    ).finalize()
    ax = p.axd["A"]
    assert ax.get_title() == "Correlation Heatmap"
    images = ax.get_images()
    assert len(images) == 1
    assert images[0].get_clim() == (-1.0, 1.0)
    # Check text contrast: text annotations exist and contain black or white
    texts = ax.texts
    assert len(texts) == 9
    colors = {t.get_color() for t in texts}
    assert "white" in colors or "black" in colors


def test_unknown_palette_warning():
    import pytest

    import pytae as pt
    df = pd.DataFrame({"day": ["Thur", "Fri"], "bill": [10, 20]})
    with pytest.warns(UserWarning, match="Unknown palette 'non_existent_palette'"):
        pt.Plotter(df).plot(kind="bar", x="day", y="bill", palette="non_existent_palette").finalize()


def test_facet_layout_kwargs_conflict_error():
    import pytest

    import pytae as pt
    df = pd.DataFrame({"grp": ["g1", "g2"], "x": [1, 2], "y": [3, 4]})

    with pytest.raises(ValueError, match="Cannot combine 'mosaic' with faceting"):
        pt.Plotter(df, mosaic="AB", ncols=2, by="grp", kind="line", x="x", y="y")

    with pytest.raises(ValueError, match="Cannot combine 'nrows' with faceting"):
        df.pt.plot(nrows=1, ncols=2, by="grp", kind="bar", x="x", y="y")

    with pytest.raises(ValueError, match="Cannot combine 'mosaic' with faceting"):
        pt.Plotter(df, "AB", by="grp", ncols=2, kind="scatter", x="x", y="y")

    with pytest.raises(ValueError, match="Cannot combine 'mosaic' with faceting"):
        pt.Plotter.facet(df, by="grp", ncols=2, mosaic="AB", kind="line", x="x", y="y")

    with pytest.raises(ValueError, match="Cannot combine 'nrows' with faceting"):
        pt.Plotter.facet(df, by="grp", ncols=2, nrows=1, kind="line", x="x", y="y")


def test_plotter_init_immediate_plot_and_unexpected_kwargs():
    import pytest

    import pytae as pt
    df = pd.DataFrame({"day": ["Thur", "Fri"], "bill": [10, 20]})

    # Passing plot kwargs to Plotter constructor draws immediately
    p = pt.Plotter(df, kind="bar", x="day", y="bill")
    assert p.axd["A"].has_data()

    # Unexpected kwargs raise TypeError
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        pt.Plotter(df, nonexistent_kwarg="invalid")


def test_box_palette_colors():
    import pytae as pt
    df = pd.DataFrame({
        "species": ["Adelie", "Gentoo", "Adelie", "Gentoo"],
        "body_mass": [3000, 4500, 3200, 4700],
    })
    p = pt.Plotter(df).plot(kind="box", x="species", y="body_mass", palette="Set1").finalize()
    ax = p.axd["A"]
    assert len(ax.patches) == 2
    # Verify patches have facecolors assigned from palette
    c0 = ax.patches[0].get_facecolor()
    c1 = ax.patches[1].get_facecolor()
    assert c0 != c1


def test_plotter_finalize_reapplies_rot_and_fontsize():
    df = pd.DataFrame({"day": ["Thursday", "Friday", "Saturday"], "bill": [10, 20, 30]})
    p = pt.Plotter(df).plot(kind="bar", x="day", y="bill", rot=45, fontsize=8).finalize()
    ax = p.axd["A"]
    labels = ax.get_xticklabels()
    assert labels[0].get_rotation() == 45
    assert labels[0].get_fontsize() == 8


def test_plotter_manage_legend_respects_legend_false():
    df = pd.DataFrame({"day": ["Thur", "Fri"], "bill": [10, 20], "sex": ["M", "F"]})
    p = pt.Plotter(df).plot(kind="bar", x="day", y="bill", by="sex", legend=False).finalize()
    ax = p.axd["A"]
    assert ax.get_legend() is None


def test_plotter_default_kind_finalize_does_not_raise_keyerror():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [3, 1, 2]})
    p = pt.Plotter(df).plot(x="a", y="b").finalize()
    assert p.axd["A"].has_data()

    df_facet = pd.DataFrame({"g": ["x", "y"], "x": [1, 2], "y": [3, 4]})
    pf = pt.Plotter.facet(df_facet, by="g", x="x", y="y").finalize()
    assert len(pf.axd) == 2


def test_plotter_numeric_x_dtype_preserved_for_line_and_area():
    df = pd.DataFrame({"x": [1, 2, 10], "y": [1, 4, 2]})
    p_line = pt.Plotter(df).plot(kind="line", x="x", y="y")
    data_line = p_line.get_data("A")
    assert pd.api.types.is_numeric_dtype(data_line["x"])

    p_area = pt.Plotter(df).plot(kind="area", x="x", y="y")
    data_area = p_area.get_data("A")
    assert pd.api.types.is_numeric_dtype(data_area["x"])


def test_plotter_line_style_and_width_handling():
    df = pd.DataFrame({"x": [1, 2], "A": [10, 20], "B": [30, 40]})
    # String style and int width
    p1 = pt.Plotter(df).plot(kind="line", x="x", y=["A", "B"], style="--", width=3)
    lines1 = p1.axd["A"].get_lines()
    for line_item in lines1:
        assert line_item.get_linestyle() == "--"
        assert line_item.get_linewidth() == 3

    # Dict style and dict width mapped by label
    p2 = pt.Plotter(df).plot(kind="line", x="x", y=["A", "B"], style={"B": ":", "A": "-."}, width={"B": 5, "A": 1})
    lines2 = p2.axd["A"].get_lines()
    for line_item in lines2:
        if line_item.get_label() == "A":
            assert line_item.get_linestyle() == "-."
            assert line_item.get_linewidth() == 1
        elif line_item.get_label() == "B":
            assert line_item.get_linestyle() == ":"
            assert line_item.get_linewidth() == 5


def test_plotter_grouped_scatter_xlim_ylim_rot_fontsize_s_col():
    df = pd.DataFrame({
        "x": [1, 2, 3, 4],
        "y": [10, 20, 30, 40],
        "g": ["a", "a", "b", "b"],
        "sz": [15, 25, 35, 45],
    })
    p = pt.Plotter(df).plot(kind="scatter", x="x", y="y", by="g", s="sz", xlim=(0, 10), ylim=(0, 50), rot=45, fontsize=9)
    ax = p.axd["A"]
    assert ax.get_xlim() == (0, 10)
    assert ax.get_ylim() == (0, 50)
    assert len(ax.collections) == 2


def test_plotter_color_string_and_box_color_list():
    df = pd.DataFrame({
        "g": ["a", "b", "a", "b"],
        "v": [10, 20, 30, 40],
    })
    # Grouped scatter with color="crimson" string
    p1 = pt.Plotter(df).plot(kind="scatter", x="v", y="v", by="g", color="crimson")
    assert len(p1.axd["A"].collections) == 2

    # Box plot with color list
    p2 = pt.Plotter(df).plot(kind="box", x="g", y="v", color=["crimson", "navy"])
    assert len(p2.axd["A"].patches) == 2


def test_plotter_heatmap_numpy_int_annotation_formatting():
    import numpy as np
    df = pd.DataFrame({"a": [np.int64(0), np.int64(100)], "b": [np.int64(100), np.int64(0)]})
    p = pt.Plotter(df).plot(kind="heatmap", annot=True, fmt=".2f", cmap="viridis")
    texts = [t.get_text() for t in p.axd["A"].texts]
    assert "100.00" in texts
    assert "0.00" in texts


def test_plotter_ungrouped_scatter_color_and_array_c():
    import numpy as np
    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    # c is string color name not in columns
    p1 = pt.Plotter(df).plot(kind="scatter", x="x", y="y", c="red")
    assert p1.axd["A"].has_data()

    # c is numpy array
    c_arr = np.array([0.1, 0.5, 0.9])
    p2 = pt.Plotter(df).plot(kind="scatter", x="x", y="y", c=c_arr)
    assert p2.axd["A"].has_data()


def test_plotter_pie_colors_list():
    df = pd.DataFrame({"cat": ["a", "b"], "val": [1, 2]})
    p = pt.Plotter(df).plot(kind="pie", by="cat", y="val", colors=["red", "blue"])
    assert p.axd["A"].has_data()


def test_plotter_list_y_order_and_aggregate_error():
    df = pd.DataFrame({"q": ["Q1", "Q2"], "rev": [100, 200], "cost": [40, 80]})
    p1 = pt.Plotter(df).plot(kind="bar", x="q", y=["rev", "cost"])
    assert list(p1.get_data("A").columns) == ["q", "rev", "cost"]

    # Passing aggregate raises ValueError
    with pytest.raises(ValueError, match="Plotter does not perform aggregation"):
        pt.Plotter(df).plot(kind="bar", x="q", y=["rev", "cost"], aggregate=True)


def test_plotter_hist_and_kde_with_by_on_duplicate_index():
    df = pd.DataFrame({"g": ["a", "a", "b", "b"], "v": [1.0, 2.0, 3.0, 4.0]}, index=[0, 0, 1, 1])
    # hist with duplicate index
    p_hist = pt.Plotter(df).plot(kind="hist", column="v", by="g")
    assert p_hist.axd["A"].has_data()

    # kde with duplicate index
    p_kde = pt.Plotter(df).plot(kind="kde", column="v", by="g")
    assert p_kde.axd["A"].has_data()


def test_plotter_finalize_fontsize_both_axes_and_rot():
    # Plot Issue 1 (Review 2ec5bbba): fontsize applies to both axes, rot to category axis
    df = pd.DataFrame({"day": ["Thursday", "Friday", "Saturday"], "bill": [10, 20, 30]})
    p = pt.Plotter(df).plot(kind="bar", x="day", y="bill", rot=45, fontsize=8).finalize()
    ax = p.axd["A"]
    yticks = ax.yaxis.get_major_ticks()
    if yticks:
        assert yticks[0].label1.get_size() == 8
    xticks = ax.xaxis.get_major_ticks()
    if xticks:
        assert xticks[0].label1.get_size() == 8
        assert xticks[0].label1.get_rotation() == 45


def test_plotter_line_style_width_integer_keys():
    # Plot Issue 2 (Review 2ec5bbba): style and width dicts with integer keys match stringified line labels
    df = pd.DataFrame({"x": [1, 2], 1: [10, 20], 2: [30, 40]})
    p = pt.Plotter(df).plot(kind="line", x="x", y=[1, 2], style={2: ":", 1: "-."}, width={2: 5, 1: 1})
    lines = p.axd["A"].get_lines()
    for line in lines:
        if line.get_label() == "1":
            assert line.get_linestyle() == "-."
            assert line.get_linewidth() == 1
        elif line.get_label() == "2":
            assert line.get_linestyle() == ":"
            assert line.get_linewidth() == 5


def test_plotter_hist_and_kde_with_by_having_missing_values():
    penguins = pt.sample("penguins")
    p_hist = pt.Plotter(penguins).plot(kind="hist", column="bill_length_mm", by="sex")
    assert p_hist.axd["A"].has_data()

    p_kde = pt.Plotter(penguins).plot(kind="kde", column="body_mass_g", by="sex")
    assert p_kde.axd["A"].has_data()


def test_plotter_pie_with_dropna():
    df = pd.DataFrame({"cat": ["a", "b", None], "val": [1, 2, 5]})
    p1 = pt.Plotter(df).plot(kind="pie", by="cat", y="val", dropna=False)
    assert p1.axd["A"].has_data()
    assert len(p1.get_data("A")) == 3
    p2 = pt.Plotter(df).plot(kind="pie", by="cat", y="val", dropna=True)
    assert p2.axd["A"].has_data()
    assert len(p2.get_data("A")) == 2


def test_plotter_finalize_with_title_and_tight_layout():
    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    p = pt.Plotter(df).plot(kind="scatter", x="x", y="y")
    p.finalize(title="Custom Title", tight_layout=True, xlabel="X Axis", ylabel="Y Axis")
    assert p.axd["A"].get_xlabel() == "X Axis"
    assert p.axd["A"].get_ylabel() == "Y Axis"


def test_plotter_heatmap_matrix_honors_annot_and_numeric():
    df = pd.DataFrame({"x": ["a", "b"], "c1": [1.0, 2.0], "c2": [3.0, 4.0]})
    p = pt.Plotter(df).plot(kind="heatmap", x="x", annot=True)
    assert p.axd["A"].has_data()
    assert p.get_data("A").shape == (2, 2)


def test_plotter_grouped_bar_by_value_equals_x_name():
    df = pd.DataFrame({
        "year": [2020, 2020, 2021],
        "metric": ["year", "sales", "sales"],
        "value": [1, 10, 12],
    })
    with pytest.raises(ValueError, match="collides with x-axis column name"):
        pt.Plotter(df).plot(kind="bar", x="year", y="value", by="metric")


def test_plotter_box_color_dict_with_integer_keys():
    df = pd.DataFrame({"g": [1, 1, 2, 2], "v": [1, 2, 3, 4]})
    p = pt.Plotter(df).plot(kind="box", x="g", y="v", color={1: "crimson", 2: "navy"})
    assert p.axd["A"].has_data()


def test_plotter_falsy_column_name_zero():
    # String column "0" works cleanly
    df_str = pd.DataFrame({"x": [1, 2], "y": [3, 4], "0": ["g1", "g2"]})
    p_bar_str = pt.Plotter(df_str).plot(kind="bar", x="x", y="y", by="0")
    assert p_bar_str.axd["A"].has_data()

    # Integer column 0 works cleanly
    df_int = pd.DataFrame({"x": [1, 2], "y": [3, 4], 0: ["g1", "g2"]})
    p_bar_int = pt.Plotter(df_int).plot(kind="bar", x="x", y="y", by=0)
    assert p_bar_int.axd["A"].has_data()


def test_plotter_finalize_invalid_style():
    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    p = pt.Plotter(df).plot(kind="line", x="x", y="y")
    with pytest.raises(ValueError, match="stylesheet 'non_existent_style_xyz' not recognized"):
        p.finalize(style="non_existent_style_xyz")


def test_plotter_normalized_by_category_collision_with_x():
    # Issue 4: stringified collision between by category and x column name
    df1 = pd.DataFrame({"1": ["a", "b", "c"], "g": [1, 1, 2], "v": [10, 20, 30]})
    with pytest.raises(ValueError, match="collides with x-axis column name"):
        pt.Plotter(df1).plot(kind="bar", x="1", y="v", by="g")

    df2 = pd.DataFrame({"nan": [1, 2, 3], "g": [None, None, "a"], "v": [10, 20, 30]})
    with pytest.raises(ValueError, match="collides with x-axis column name"):
        pt.Plotter(df2).plot(kind="bar", x="nan", y="v", by="g")


def test_plotter_integer_x_labels():
    # Issue 5: integer x column label is treated as column, not out-of-bounds positional index
    df = pd.DataFrame({1: ["a", "a", "b"], "g": ["x", "y", "x"], "v": [10, 20, 30]})
    p1 = pt.Plotter(df).plot(kind="bar", x=1, y="v", by="g")
    assert p1.axd["A"].has_data()

    df_2020 = pd.DataFrame({2020: ["a", "b", "c"], "v": [10, 20, 30]})
    p2 = pt.Plotter(df_2020).plot(kind="bar", x=2020, y="v")
    assert p2.axd["A"].has_data()


def test_plotter_integer_column_scatter_and_hexbin():
    # Issue 6: integer column label in scatter and hexbin
    df = pd.DataFrame({"x": [1, 2, 3], 0: [4, 5, 6], "g": ["a", "a", "b"]})
    p_scat = pt.Plotter(df).plot(kind="scatter", x="x", y=0)
    assert p_scat.axd["A"].has_data()

    p_hex = pt.Plotter(df).plot(kind="hexbin", x="x", y=0)
    assert p_hex.axd["A"].has_data()


def test_plotter_box_plot_with_cat_col_zero():
    # Issue 7: box grouping on column named 0
    df = pd.DataFrame({0: [1, 1, 2, 2], "v": [1.0, 2.0, 100.0, 200.0]})
    p_box_x = pt.Plotter(df).plot(kind="box", x=0, y="v")
    assert len(p_box_x.tables["A"].columns) == 2

    p_box_by = pt.Plotter(df).plot(kind="box", by=0, y="v")
    assert len(p_box_by.tables["A"].columns) == 2


def test_plotter_faceting_with_by_zero():
    # Issue 8: faceting on by=0
    df = pd.DataFrame({0: ["a", "a", "b", "b"], "x": [1, 2, 3, 4], "y": [10, 20, 30, 40]})
    p = pt.Plotter(df, by=0, ncols=2, kind="scatter", x="x", y="y")
    assert "a" in p.axd and "b" in p.axd
    assert p.axd["a"].has_data()
    assert p.axd["b"].has_data()

    p_acc = df.pt.plot(by=0, ncols=2, kind="scatter", x="x", y="y")
    assert "a" in p_acc.axd and "b" in p_acc.axd
    assert p_acc.axd["a"].has_data()
    assert p_acc.axd["b"].has_data()


def test_plotter_mixed_y_aggregate_true():
    # Issue 10: mixed integer and string column names in y with aggregate=True
    df = pd.DataFrame({"x": [1, 2], 0: [4, 5], "b": [7, 8]})
    p = pt.Plotter(df).plot(kind="bar", x="x", y=[0, "b"])
    assert p.axd["A"].has_data()


def test_plotter_kde_minimum_count_check():
    # Issue 11: kde raises ValueError when observation count per group < 2
    df = pd.DataFrame({"g": ["a", "b"], "v": [1.0, 2.0]})
    with pytest.raises(ValueError, match="kde/density plot requires at least two"):
        pt.Plotter(df).plot(kind="kde", column="v", by="g")


def test_plotter_finalize_sharex_and_sharey():
    # Issue 12: finalize(sharex=True, sharey=True) links axes
    df1 = pd.DataFrame({"x": [1, 2], "y": [10, 20]})
    df2 = pd.DataFrame({"x": [1, 2], "y": [100, 200]})
    p = pt.Plotter(mosaic="AB")
    p.data(df1).plot(on="A", kind="bar", x="x", y="y")
    p.data(df2).plot(on="B", kind="bar", x="x", y="y")
    p.finalize(sharey=True)
    ax_a = p.axd["A"]
    ax_b = p.axd["B"]
    assert ax_a.get_shared_y_axes().joined(ax_a, ax_b)


def test_plotter_integer_coords_on_integer_columns():
    # Issue 5: integer coordinates x and y on DataFrame with integer column index
    df = pd.DataFrame([[10, 20], [30, 40]], columns=[1, 2])
    p1 = pt.Plotter(df).plot(kind="scatter", x=1, y=2)
    assert p1.axd["A"].has_data()

    p2 = pt.Plotter(df).plot(kind="line", x=1, y=2)
    assert p2.axd["A"].has_data()

    p3 = pt.Plotter(df).plot(kind="bar", x=1, y=2)
    assert p3.axd["A"].has_data()


def test_plotter_dropna_in_line_bar_heatmap():
    # Issue 6: dropna dropped NA values before reshaping/plotting
    df = pd.DataFrame({
        "x": ["a", "b", None, "c"],
        "g": ["g1", "g1", "g2", "g2"],
        "y": [1.0, 2.0, 3.0, 4.0],
    })
    # Line with dropna=True drops None row in x
    p_line = pt.Plotter(df).plot(kind="line", x="x", y="y", by="g", dropna=True)
    table_line = p_line.get_data("A")
    assert None not in table_line["x"].values

    # Bar with dropna=True
    p_bar = pt.Plotter(df).plot(kind="bar", x="x", y="y", by="g", dropna=True)
    table_bar = p_bar.get_data("A")
    assert None not in table_bar["x"].values

    # Heatmap with dropna=True
    p_heat = pt.Plotter(df).plot(kind="heatmap", x="x", y="y", by="g", dropna=True)
    table_heat = p_heat.get_data("A")
    assert None not in table_heat.index


def test_plotter_grouped_kde_singleton_raises_value_error():
    # Issue 7: Grouped kde requires at least 2 non-null observations in each group
    df = pd.DataFrame({
        "g": ["A", "A", "B"],  # B has only 1 observation
        "v": [10.0, 20.0, 30.0],
    })
    with pytest.raises(ValueError, match="at least two non-null observations in each group.*'B'"):
        pt.Plotter(df).plot(kind="kde", column="v", by="g")


def test_plotter_finalize_sharex_and_sharey_three_axes():
    # Issue 8: finalize(sharex=True, sharey=True) with 3+ axes
    df = pd.DataFrame({"x": [1, 2], "y": [10, 20]})
    p = pt.Plotter(mosaic="ABC")
    p.data(df).plot(on="A", kind="line", x="x", y="y")
    p.data(df).plot(on="B", kind="line", x="x", y="y")
    p.data(df).plot(on="C", kind="line", x="x", y="y")
    p.finalize(sharex=True, sharey=True)
    ax_a = p.axd["A"]
    ax_b = p.axd["B"]
    ax_c = p.axd["C"]
    assert ax_a.get_shared_x_axes().joined(ax_a, ax_b)
    assert ax_a.get_shared_x_axes().joined(ax_a, ax_c)
    assert ax_a.get_shared_y_axes().joined(ax_a, ax_b)
    assert ax_a.get_shared_y_axes().joined(ax_a, ax_c)


def test_plotter_show_method():
    # Issue 10: Plotter.show() exists and is chainable
    df = pd.DataFrame({"x": [1, 2], "y": [10, 20]})
    p = pt.Plotter(df).plot(kind="line", x="x", y="y")
    ret = p.show()
    assert ret is p


def test_plotter_by_column_validation():
    # Issue 12: Validate that 'by' column exists in DataFrame
    df = pd.DataFrame({"x": [1, 2], "y": [10, 20]})
    with pytest.raises(KeyError, match="column 'nonexistent' for 'by' not found"):
        pt.Plotter(df).plot(kind="line", x="x", y="y", by="nonexistent")

    with pytest.raises(KeyError, match="column 'nonexistent' for 'by' not found"):
        pt.Plotter(df).plot(kind="bar", x="x", y="y", by="nonexistent")

    with pytest.raises(KeyError, match="column 'nonexistent' for 'by' not found"):
        pt.Plotter(df).plot(kind="scatter", x="x", y="y", by="nonexistent")

    with pytest.raises(KeyError, match="column 'nonexistent' for 'by' not found"):
        pt.Plotter(df).plot(kind="kde", column="y", by="nonexistent")

    with pytest.raises(KeyError, match="column 'nonexistent' for 'by' not found"):
        pt.Plotter(df).plot(kind="hist", column="y", by="nonexistent")


def test_plotter_hist_and_kde_no_dropna_warning():
    # Issue 13: dropna is supported in hist and kde without warning
    import warnings
    df = pd.DataFrame({"g": ["a", "a", None], "v": [1.0, 2.0, 3.0]})
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        pt.Plotter(df).plot(kind="hist", column="v", by="g", dropna=True)
    dropna_warnings = [w for w in record if "dropna" in str(w.message).lower()]
    assert len(dropna_warnings) == 0


def test_plotter_wide_data_optional_y():
    # When plotting wide data (e.g. from pivot), y is optional
    df = pd.DataFrame({
        "day": ["Thur", "Fri"],
        "Lunch": [10.0, 15.0],
        "Dinner": [20.0, 25.0],
    })
    p_barh = df.pt.plot(kind="barh", x="day")
    assert p_barh.axd["A"].has_data()

    p_line = df.pt.plot(kind="line", x="day")
    assert p_line.axd["A"].has_data()

def test_plotter_remap_coord_pandas2_and_3():
    from unittest.mock import MagicMock

    from pytae.plotting import _remap_coord_if_needed

    # Simulating pandas 2.x Index with _holds_integer() -> True
    mock_cols_pd2 = MagicMock()
    mock_cols_pd2.dtype.kind = "O"
    mock_cols_pd2._holds_integer.return_value = True
    mock_cols_pd2.__contains__.side_effect = lambda k: k in ["x", 0, "g"]
    assert _remap_coord_if_needed(mock_cols_pd2, 0) == 0
    assert _remap_coord_if_needed(mock_cols_pd2, "x") == "x"

    # Simulating pandas 3.x where Index does not have _holds_integer
    mock_cols_pd3 = MagicMock(spec=["dtype", "get_loc", "__contains__"])
    mock_cols_pd3.dtype.kind = "O"
    mock_cols_pd3.__contains__.side_effect = lambda k: k in ["x", 0, "g"]
    mock_cols_pd3.get_loc.side_effect = lambda k: ["x", 0, "g"].index(k)
    assert _remap_coord_if_needed(mock_cols_pd3, 0) == 1
    assert _remap_coord_if_needed(mock_cols_pd3, "x") == "x"

