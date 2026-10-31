import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytae as pt


def test_pt_accessor_select_then_agg():
    penguins = pt.sample("penguins")
    out = penguins.pt.by("species", "island").pt.agg(a=["mean", "n"])
    assert list(out.columns)[:3] == ["species", "island", "n"]


def test_pandas_rename_then_pt_agg():
    df = pd.DataFrame({"g": ["a", "a", "b"], "v": [1, 2, 3]})
    out = df.rename(columns={"g": "grp", "v": "val"}).pt.by("grp").pt.agg(a=["sum", "n"])
    assert list(out.columns) == ["grp", "n", "val"]
    assert out.loc[out["grp"] == "a", "val"].iloc[0] == 3


def test_pt_accessor_agg_df_deprecated():
    import pytest

    df = pd.DataFrame({"g": ["a", "b"], "v": [1, 2]})
    with pytest.raises(AttributeError, match="df.pt.agg_df.*removed; use df.pt.agg"):
        df.pt.agg_df("g")


def test_pt_select_then_pandas_head():
    penguins = pt.sample("penguins")
    out = penguins.pt.select("species", "body_mass_g").head(3)
    assert list(out.columns) == ["species", "body_mass_g"]
    assert len(out) == 3


def test_pt_accessor_safe_reset_index():
    df = pd.DataFrame({"a": [1, 2]}, index=pd.Index(["x", "y"], name="idx"))
    res = df.pt.safe_reset_index()
    assert list(res.columns) == ["idx", "a"]
    assert list(res["idx"]) == ["x", "y"]


def test_pt_accessor_to_clip(monkeypatch):
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    clip_called = []

    def mock_to_clipboard(self, *args, **kwargs):
        clip_called.append((args, kwargs))

    monkeypatch.setattr(pd.DataFrame, "to_clipboard", mock_to_clipboard)
    df.pt.to_clip()
    assert len(clip_called) == 1
    assert clip_called[0][1].get("index") is False


def test_pt_accessor_dropna_pandas_and_polars():
    import polars as pl

    pdf = pd.DataFrame({"a": [1.0, None, 3.0], "b": [10.0, 20.0, 30.0]})
    pldf = pl.DataFrame({"a": [1.0, None, 3.0], "b": [10.0, 20.0, 30.0]})

    # Zero-Data-Loss: bare dropna on partially null rows keeps all rows
    assert len(pdf.pt.dropna()) == 3
    assert len(pldf.pt.dropna()) == 3

    # Targeted dropna on column 'a' drops the null row
    assert len(pdf.pt.dropna("a")) == 2
    assert len(pldf.pt.dropna("a")) == 2

    # Renaming via .pt
    pdf_renamed = pdf.pt.rename("a:alpha, b:beta")
    assert list(pdf_renamed.columns) == ["alpha", "beta"]
    pldf_renamed = pldf.pt.rename(a="alpha")
    assert "alpha" in pldf_renamed.columns

    # SQL via .pt
    pdf_sql = pdf.pt.sql("SELECT b FROM data WHERE b IS NOT NULL")
    assert len(pdf_sql) == 3
    pldf_sql = pldf.pt.sql("SELECT a FROM data WHERE a IS NOT NULL")
    assert len(pldf_sql) == 2


def test_pt_sample_datasets_and_row_sampling():
    import polars as pl

    # 1. Bundled dataset loading
    penguins = pt.sample("penguins")
    assert len(penguins) == 344
    assert len(pt.sample()) == 344
    assert len(pt.sample_data["tips"]) == 244

    # 2. DataFrame.sample()
    s1 = penguins.sample(5, seed=42)
    assert len(s1) == 5
    assert isinstance(s1, pt.DataFrame)

    # 3. df.pt.sample() on pytae DataFrame
    s2 = penguins.pt.sample(frac=0.1, seed=42)
    assert len(s2) == 34

    # 4. pt.sample(df, ...) top-level verb
    s3 = pt.sample(penguins, 10, seed=42)
    assert len(s3) == 10

    # 5. Pandas DataFrame with .pt.sample()
    pdf = pd.DataFrame({"x": range(100)})
    s4 = pdf.pt.sample(7, seed=42)
    assert len(s4) == 7

    # 6. Polars DataFrame with .pt.sample()
    pldf = pl.DataFrame({"x": range(100)})
    s5 = pldf.pt.sample(8, seed=42)
    assert len(s5) == 8

    # 7. Grouped sampling
    p_grouped = penguins.pt.by("species").sample(2, seed=42)
    assert len(p_grouped) == 6  # 3 species * 2 rows


def test_polars_lazyframe_pt_accessor():
    import polars as pl

    ldf = pl.LazyFrame({"a": [1, 2, 3], "b": [10, 20, 30]})
    # Test entering Pytae from native pl.LazyFrame via .pt
    plan = ldf.pt.mutate(c="a + b").with_columns(d=pl.col("c") * 2).filter("d > 30").arrange("d desc").select("a", "d")
    assert plan.is_lazy
    collected = plan.collect()
    assert isinstance(collected, pt.DataFrame)
    assert not collected.is_lazy
    assert list(collected.columns) == ["a", "d"]
    assert list(collected["a"]) == [3, 2]
    assert list(collected["d"]) == [66, 44]


def test_polars_pt_accessor_first_call_native_verb():
    import polars as pl

    pldf = pl.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    # Calling native Polars verb directly on .pt accessor enters pytae.DataFrame
    out = pldf.pt.with_columns(z=pl.col("x") + pl.col("y")).mutate(double_z="z * 2")
    assert isinstance(out, pt.DataFrame)
    assert list(out.columns) == ["x", "y", "z", "double_z"]
    assert list(out["double_z"]) == [10, 14, 18]


def test_pt_accessor_by_auto_ungroups(tmp_path):
    import pytest

    parquet_path = tmp_path / "data.parquet"
    df_raw = pd.DataFrame({"species": ["A", "A", "B", "B"], "mass": [10.0, 20.0, 100.0, 200.0]})
    df_raw.to_parquet(parquet_path)

    # 1. Loading from parquet
    k = pt.read_parquet(parquet_path)
    assert isinstance(k, pt.DataFrame)

    # 2. k.by() with no arguments raises ValueError
    with pytest.raises(ValueError, match=r"df\.pt\.by\(\) takes at least one column name"):
        k.by()

    # 3. .by() scopes the immediate next mutate, which automatically returns an ungrouped DataFrame
    k_res = k.by("species").mutate(group_mean="mean(mass)").mutate(overall_mean="mean(mass)")
    assert isinstance(k_res, pt.DataFrame)
    assert k_res["group_mean"].to_list() == [15.0, 15.0, 150.0, 150.0]
    assert k_res["overall_mean"].to_list() == [82.5, 82.5, 82.5, 82.5]


def test_pt_accessor_comprehensive_shared_verbs(capsys):
    import polars as pl
    import pytest

    sample_pl = pl.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "grp": ["A", "A", "B", "B"],
            "val": [10.0, 20.0, None, 40.0],
            "other": [1.0, 2.0, 3.0, 4.0],
        }
    )
    sample_pd = sample_pl.to_pandas()

    for obj in (sample_pl, sample_pl.lazy(), sample_pd):
        def _collect(res):
            return res.collect() if res.is_lazy else res

        assert len(_collect(obj.pt.filter("id > 2"))) == 2
        assert list(_collect(obj.pt.select("id, grp")).columns) == ["id", "grp"]
        assert _collect(obj.pt.arrange("id desc"))["id"].to_list() == [4, 3, 2, 1]
        assert len(_collect(obj.pt.distinct("grp"))) == 2
        assert _collect(obj.pt.count("grp"))["n"].to_list() == [2, 2]
        assert len(_collect(obj.pt.dropna("val"))) == 3
        assert _collect(obj.pt.fillna(0.0, "val"))["val"].to_list() == [10.0, 20.0, 0.0, 40.0]
        assert len(_collect(obj.pt.head(2))) == 2
        assert len(_collect(obj.pt.tail(2))) == 2
        assert _collect(obj.pt.mutate("doubled = other * 2"))["doubled"].to_list() == [2.0, 4.0, 6.0, 8.0]
        assert list(_collect(obj.pt.rename("grp:group")).columns) == ["id", "group", "val", "other"]
        assert _collect(obj.pt.by("grp").agg("s = sum(other)")).shape == (2, 2)
        assert _collect(obj.pt.agg("s = sum(other)"))["s"].to_list() == [10.0]
        assert _collect(obj.pt.pipe(lambda d: d.head(1))).shape == (1, 4)

    for obj in (sample_pl, sample_pd):
        # pivot, long, wide
        piv = obj.pt.fillna(0.0, "val").pivot(r="grp", c="id", v="other", a="sum")
        assert "grp" in piv.columns
        melted = obj.pt.long(cols=["val", "other"], id_vars="id")
        assert set(melted.columns) == {"id", "variable", "value"}
        unmelted = melted.to_polars().pt.wide(r="id", c="variable", v="value")
        assert "other" in unmelted.columns

        # clean_columns, mask, unmask
        messy = (
            pl.DataFrame({"Bad Col": ["secret"]})
            if isinstance(obj, pl.DataFrame)
            else pd.DataFrame({"Bad Col": ["secret"]})
        )
        assert messy.pt.clean_columns(case="lower", fill="_").columns == ["bad_col"]
        masked = obj.pt.mask("grp=encrypt", key="secret_key")
        assert masked["grp"].to_list() != ["A", "A", "B", "B"]
        unmasked = masked.to_polars().pt.unmask("grp", key="secret_key")
        assert unmasked["grp"].to_list() == ["A", "A", "B", "B"]

        # cols, diff, glimpse
        assert obj.pt.cols() == ["grp", "id", "other", "val"]
        assert "Identical" in obj.pt.diff(obj)
        assert obj.pt.glimpse() is obj
        _ = capsys.readouterr()

        # freq, hist, bar, scatter, corr
        assert len(obj.pt.freq("grp")) == 2
        assert len(obj.pt.hist("other", bins=2)) == 2
        assert len(obj.pt.bar("grp", "other")) == 4
        assert isinstance(obj.pt.scatter("id", "other", width=20, height=5), str)
        assert len(obj.pt.corr()) >= 1

        # join & concat
        right = pl.DataFrame({"id": [1, 2], "tag": ["x", "y"]})
        joined = obj.pt.join(right, on="id", how="inner")
        assert len(joined) == 2
        stacked = obj.pt.concat(obj)
        assert len(stacked) == 8

        # conversions and fallback getattr
        assert isinstance(obj.pt.to_polars(), pl.DataFrame)
        assert isinstance(obj.pt.to_pandas(), pd.DataFrame)
        assert obj.pt.shape == (4, 4)

        # retired pick() and invalid agg(by=...) error paths
        with pytest.raises(AttributeError, match="pick\\(\\) has been removed"):
            obj.pt.pick("id")
        with pytest.raises(TypeError, match="does not accept 'by'"):
            obj.pt.agg("count", by="grp")

