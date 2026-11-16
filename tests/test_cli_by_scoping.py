import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from pytae.repl import PytaeRepl
from tests.cli_helpers import _write_csv


def test_sequential_by_mutate_single_shot(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "region": ["East", "East", "West", "West"],
            "sales": [10.0, 30.0, 100.0, 200.0],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main(
        [
            path,
            "-by",
            "region",
            "-mutate",
            "regional_mean = mean(sales)",
            "-mutate",
            "global_mean = mean(sales)",
            "-select",
            "region,sales,regional_mean,global_mean",
            "-head",
            "4",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    # Regional means: East is 20.0, West is 150.0
    # Global mean: (10 + 30 + 100 + 200) / 4 = 85.0
    assert "20.0" in out
    assert "150.0" in out
    assert "85.0" in out


def test_sequential_by_multi_grouping(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "region": ["North", "North", "South", "South"],
            "dept": ["A", "B", "A", "B"],
            "val": [10.0, 20.0, 30.0, 40.0],
        }
    )
    path = _write_csv(tmp_path, df)

    exit_code = cli.main(
        [
            path,
            "-by",
            "region",
            "-mutate",
            "r_mean = mean(val)",
            "-by",
            "dept",
            "-mutate",
            "d_mean = mean(val)",
            "-mutate",
            "g_mean = mean(val)",
            "-select",
            "region,dept,val,r_mean,d_mean,g_mean",
            "-head",
            "4",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    # Region means: North=15.0, South=35.0
    # Dept means: A=(10+30)/2=20.0, B=(20+40)/2=30.0
    # Global mean: 25.0
    assert "15.0" in out
    assert "35.0" in out
    assert "20.0" in out
    assert "30.0" in out
    assert "25.0" in out


def test_sequential_by_head_single_shot(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["A", "A", "A", "B", "B", "B"],
            "val": [1, 2, 3, 4, 5, 6],
        }
    )
    path = _write_csv(tmp_path, df)

    # First -head 2 slices 2 per group (4 rows total: 2 from A, 2 from B)
    # Second -head 3 slices 3 rows globally from the 4 rows
    exit_code = cli.main([path, "-by", "grp", "-head", "2", "-head", "3", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(3, 2)"


def test_sequential_by_tail_single_shot(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["A", "A", "A", "B", "B", "B"],
            "val": [1, 2, 3, 4, 5, 6],
        }
    )
    path = _write_csv(tmp_path, df)

    # First -tail 2 slices 2 per group (4 rows total: 2 from A, 2 from B)
    # Second -tail 3 slices 3 rows globally from the 4 rows
    exit_code = cli.main([path, "-by", "grp", "-tail", "2", "-tail", "3", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(3, 2)"


def test_sequential_by_sample_single_shot(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["A", "A", "A", "B", "B", "B"],
            "val": [1, 2, 3, 4, 5, 6],
        }
    )
    path = _write_csv(tmp_path, df)

    # First -sample 2 samples 2 per group (4 rows)
    # Second -sample 3 samples 3 rows globally from the 4
    exit_code = cli.main([path, "-by", "grp", "-sample", "2", "-sample", "3", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(3, 2)"


def test_sequential_by_count_single_shot(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["A", "A", "B", "B", "B"],
            "val": [1, 2, 3, 4, 5],
        }
    )
    path = _write_csv(tmp_path, df)

    # First -count produces grouped count (2 rows: A=2, B=3)
    # Second -count counts the rows of that table (1 row: n=2)
    exit_code = cli.main([path, "-by", "grp", "-count", "-count", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(1, 1)"


def test_sequential_by_arrange_slice_scoping(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "grp": ["A", "A", "B", "B"],
            "val": [10, 20, 100, 200],
        }
    )
    path = _write_csv(tmp_path, df)

    # -by grp -arrange val desc -head 1 takes highest val per group (2 rows: A:20, B:200)
    # followed by -mutate "total=sum(val)" which computes global sum (220)
    exit_code = cli.main(
        [
            path,
            "-by",
            "grp",
            "-arrange",
            "val.desc()",
            "-head",
            "1",
            "-mutate",
            "total = sum(val)",
            "-select",
            "grp,val,total",
            "-head",
            "2",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "220" in out


def test_trailing_by_rejected(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["A", "B"], "val": [1, 2]})
    path = _write_csv(tmp_path, df)

    with pytest.raises(SystemExit):
        cli.main([path, "-mutate", "val2 = val * 2", "-by", "grp"])
    err = capsys.readouterr().err
    assert "-by requires -agg, -mutate, -head, -tail, -count, or -sample to follow it" in err


def test_bare_by_rejected(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["A", "B"], "val": [1, 2]})
    path = _write_csv(tmp_path, df)

    with pytest.raises(SystemExit):
        cli.main([path, "-by", "grp"])
    err = capsys.readouterr().err
    assert "-by requires -agg, -mutate, -head, -tail, -count, or -sample to follow it" in err


def test_misplaced_by_before_select_rejected(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["A", "B"], "val": [1, 2]})
    path = _write_csv(tmp_path, df)

    with pytest.raises(SystemExit):
        cli.main([path, "-by", "grp", "-select", "grp,val"])
    err = capsys.readouterr().err
    assert "-by requires -agg, -mutate, -head, -tail, -count, or -sample to follow it" in err


def test_misplaced_by_before_filter_rejected(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["A", "B"], "val": [1, 2]})
    path = _write_csv(tmp_path, df)

    with pytest.raises(SystemExit):
        cli.main([path, "-by", "grp", "-filter", "val > 1", "-mutate", "v2 = val * 2"])
    err = capsys.readouterr().err
    assert "-by requires -agg, -mutate, -head, -tail, -count, or -sample to follow it" in err


def test_sequential_by_agg_single_shot(tmp_path, capsys):
    df = pd.DataFrame(
        {
            "region": ["East", "East", "West", "West"],
            "sales": [10.0, 30.0, 100.0, 200.0],
        }
    )
    path = _write_csv(tmp_path, df)

    # -by region -agg "tot=sum(sales)" produces 2 rows (East: 40, West: 300)
    # followed by -mutate "pct=tot/sum(tot)" which is global sum (340)
    exit_code = cli.main(
        [
            path,
            "-by",
            "region",
            "-agg",
            "tot = sum(sales)",
            "-mutate",
            "pct = tot / sum(tot)",
            "-head",
            "2",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    # 40 / 340 ~ 0.1176, 300 / 340 ~ 0.8823
    assert "0.1176" in out or "0.118" in out or "0.12" in out


def test_by_unknown_column_rejected(tmp_path, capsys):
    df = pd.DataFrame({"grp": ["A", "B"], "val": [1, 2]})
    path = _write_csv(tmp_path, df)

    with pytest.raises(SystemExit):
        cli.main([path, "-by", "non_existent", "-mutate", "v2 = val * 2"])
    err = capsys.readouterr().err
    assert "unknown column(s): 'non_existent'" in err


def test_repl_sequential_by_single_shot():
    repl = PytaeRepl()
    outputs: list[str] = []

    repl.execute_line("df = sample:penguins", output_fn=outputs.append)
    outputs.clear()

    # 1. Bare preview
    repl.execute_line(
        '-by species -mutate "mean_mass=mean(body_mass_g)" -mutate "global_mass=mean(body_mass_g)"',
        output_fn=outputs.append,
    )
    combined = "\n".join(outputs)
    assert "3700.662252" in combined
    assert "5076.016260" in combined
    assert "4201.754386" in combined

    # 2. Assignment
    outputs.clear()
    repl.execute_line(
        'df = df -by species -mutate "mean_mass=mean(body_mass_g)" -mutate "global_mass=mean(body_mass_g)"',
        output_fn=outputs.append,
    )
    df = repl.tables["df"]
    if hasattr(df, "collect"):
        df = df.collect()
    pdf = df.to_pandas()
    adelie_rows = pdf[pdf["species"] == "Adelie"]
    first_adelie = adelie_rows.iloc[0]
    assert round(first_adelie["mean_mass"], 2) == 3700.66
    assert round(first_adelie["global_mass"], 2) == 4201.75

    gentoo_rows = pdf[pdf["species"] == "Gentoo"]
    first_gentoo = gentoo_rows.iloc[0]
    assert round(first_gentoo["mean_mass"], 2) == 5076.02
    assert round(first_gentoo["global_mass"], 2) == 4201.75

    repl.close()
