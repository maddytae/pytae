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
    p = pt.Plotter(df, kind="bar", x="day", y="bill", aggfunc="mean")
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
    df = pd.DataFrame({"cat": ["a", "a", "b"], "val": [1, 2, 3]})
    p = pt.Plotter(df).plot(kind="pie", by="cat", y="val", colors=["red", "blue"])
    assert p.axd["A"].has_data()


def test_plotter_get_pivot_data_list_y_order_and_aggregate_false():
    df = pd.DataFrame({"q": ["Q1", "Q2"], "rev": [100, 200], "cost": [40, 80]})
    # aggregate=False with list y
    p1 = pt.Plotter(df).plot(kind="bar", x="q", y=["rev", "cost"], aggregate=False)
    assert list(p1.get_data("A").columns) == ["q", "rev", "cost"]

    # aggregate=True preserves requested y order
    p2 = pt.Plotter(df).plot(kind="bar", x="q", y=["rev", "cost"], aggregate=True)
    assert list(p2.get_data("A").columns) == ["q", "rev", "cost"]


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



