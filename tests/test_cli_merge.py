import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from pytae import cli
from tests.cli_helpers import _write_csv, _write_three_id_csvs, _write_two_csvs


def test_merge_on_differing_column_names(tmp_path, capsys):
    left, right = _write_two_csvs(tmp_path)

    cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-merge", "left=df1,right=df2,on=col a:cola",
    ])

    out = capsys.readouterr().out.strip()
    assert "val_l" in out and "val_r" in out
    assert len(out.splitlines()) == 3  # header + 2 matching rows (inner join)

def test_merge_on_pair_quoting_is_optional(tmp_path, capsys):
    left, right = _write_two_csvs(tmp_path)

    cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-merge", "left=df1,right=df2,on=col a:'cola'",
    ])

    out = capsys.readouterr().out.strip()
    assert "val_l" in out and "val_r" in out
    assert len(out.splitlines()) == 3

def test_merge_shared_column_name_outer_join(tmp_path, capsys):
    left = tmp_path / "a.csv"
    right = tmp_path / "b.csv"
    pd.DataFrame({"id": [1, 2, 3], "x": ["a", "b", "c"]}).to_csv(left, index=False)
    pd.DataFrame({"id": [1, 2, 4], "y": ["p", "q", "r"]}).to_csv(right, index=False)

    cli.main([
        "-file", f"{left}=a;{right}=b",
        "-merge", "left=a,right=b,on=id,how=outer", "-shape",
    ])

    assert capsys.readouterr().out.strip() == "(4, 3)"

def test_merge_requires_file(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-merge", "left=df1,right=df2,on=id"])
    assert exc_info.value.code == 2

def test_file_requires_merge(tmp_path):
    left, right = _write_two_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{left}=df1;{right}=df2", "-shape"])
    assert exc_info.value.code == 2

def test_file_cannot_combine_with_positional_path(tmp_path):
    left, right = _write_two_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([left, "-file", f"{left}=df1;{right}=df2", "-merge", "left=df1,right=df2,on=col a:cola"])
    assert exc_info.value.code == 2

def test_merge_unknown_alias_errors(tmp_path):
    left, right = _write_two_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{left}=df1;{right}=df2", "-merge", "left=df1,right=bogus,on=col a:cola"])
    assert exc_info.value.code == 2

def test_merge_convert_requires_output(tmp_path):
    left, right = _write_two_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{left}=df1;{right}=df2", "-merge", "left=df1,right=df2,on=col a:cola", "-convert"])
    assert exc_info.value.code == 2

def test_merge_must_be_first_op_with_file(tmp_path):
    left, right = _write_two_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([
            "-file", f"{left}=df1;{right}=df2",
            "-shape",
            "-merge", "left=df1,right=df2,on=col a:cola",
        ])
    assert exc_info.value.code == 2

def test_merge_chained_via_data_alias(tmp_path, capsys):
    a, b, c = _write_three_id_csvs(tmp_path)

    cli.main([
        "-file", f"{a}=a;{b}=b;{c}=c",
        "-merge", "left=a,right=b,on=id",
        "-merge", "left=data,right=c,on=id",
    ])

    out = capsys.readouterr().out
    assert all(col in out for col in ("x", "y", "z"))

def test_merge_data_not_available_before_anything_produced(tmp_path, capsys):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{a}=a;{b}=b", "-merge", "left=data,right=b,on=id"])
    assert exc_info.value.code == 2
    assert "'data' isn't available yet" in capsys.readouterr().err

def test_concat_stacks_three_frames_with_reset_index(tmp_path, capsys):
    a, b, c = _write_three_id_csvs(tmp_path)

    cli.main(["-file", f"{a}=a;{b}=b;{c}=c", "-concat", "frames='a,b,c'"])

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1 + 3 + 3 + 2  # header + 3 rows from each of a, b, c

def test_concat_resets_index(tmp_path, capsys, monkeypatch):
    a, b, _ = _write_three_id_csvs(tmp_path)
    copied = {}

    def _fake_to_clipboard(self, *args, **kwargs):
        copied["frame"] = self.copy()

    monkeypatch.setattr(pd.DataFrame, "to_clipboard", _fake_to_clipboard)

    cli.main(["-file", f"{a}=a;{b}=b", "-concat", "frames='a,b'", "-snip"])

    result = copied["frame"]
    assert list(result.index) == list(range(len(result)))

def test_concat_chained_via_data_alias(tmp_path, capsys):
    a, b, c = _write_three_id_csvs(tmp_path)

    cli.main([
        "-file", f"{a}=a;{b}=b;{c}=c",
        "-concat", "frames='a,b'",
        "-concat", "frames='data,c'",
        "-shape",
    ])

    assert capsys.readouterr().out.strip() == "(8, 4)"

def test_concat_requires_file(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1]}))

    with pytest.raises(SystemExit) as exc_info:
        cli.main([path, "-concat", "frames='a,b'"])
    assert exc_info.value.code == 2

def test_concat_unknown_alias_errors(tmp_path, capsys):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{a}=a;{b}=b", "-concat", "frames='a,bogus'"])
    assert exc_info.value.code == 2
    assert "unknown -file alias" in capsys.readouterr().err

def test_file_dlim_and_encoding_overrides_applied(tmp_path, capsys):
    pipe_path = tmp_path / "pipe.csv"
    pipe_path.write_bytes("id|name\n1|caf\xe9\n".encode("latin-1"))
    plain_path = tmp_path / "plain.csv"
    pd.DataFrame({"id": [2], "name": ["bravo"]}).to_csv(plain_path, index=False)

    cli.main([
        "-file", f"{pipe_path}=p,dlim=|,encoding=latin-1; {plain_path}=q",
        "-concat", "frames='p,q'",
    ])

    out = capsys.readouterr().out
    assert "café" in out
    assert "bravo" in out

def test_file_requires_at_least_two_entries(tmp_path):
    path = _write_csv(tmp_path, pd.DataFrame({"a": [1]}))

    with pytest.raises(SystemExit, match="at least two"):
        cli.main(["-file", f"{path}=a", "-concat", "frames='a,a'"])

def test_concat_requires_at_least_two_frame_names(tmp_path):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit, match="frames= needs at least two names"):
        cli.main(["-file", f"{a}=a;{b}=b", "-concat", "frames=a"])

def test_file_duplicate_alias_errors(tmp_path):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit, match="duplicate alias"):
        cli.main(["-file", f"{a}=x;{b}=x", "-concat", "frames='x,x'"])

def test_merge_on_mixed_style_errors(tmp_path):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit, match="mixes plain columns and left:right pairs"):
        cli.main(["-file", f"{a}=a;{b}=b", "-merge", "left=a,right=b,on='id:id,x'"])

def test_merge_missing_required_keys_errors(tmp_path):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit, match="missing required key"):
        cli.main(["-file", f"{a}=a;{b}=b", "-merge", "left=a"])

def test_merge_how_cross_does_not_require_on(tmp_path, capsys):
    a, b, _ = _write_three_id_csvs(tmp_path)

    cli.main(["-file", f"{a}=a;{b}=b", "-merge", "left=a,right=b,how=cross"])
    out = capsys.readouterr().out.strip()
    assert len(out.splitlines()) == 1 + 3 * 3  # header + 3x3 cross join rows

def test_merge_how_cross_rejects_on(tmp_path):
    a, b, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit, match="on= cannot be used with how=cross"):
        cli.main(["-file", f"{a}=a;{b}=b", "-merge", "left=a,right=b,how=cross,on=id"])

def test_merge_validate_failure_errors(tmp_path, capsys):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    pd.DataFrame({"id": [1, 1, 2], "x": ["a", "b", "c"]}).to_csv(left, index=False)
    pd.DataFrame({"id": [1, 2], "y": ["p", "q"]}).to_csv(right, index=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([
            "-file", f"{left}=l;{right}=r",
            "-merge", "left=l,right=r,on=id,validate=one_to_one",
        ])
    assert exc_info.value.code == 2
    assert "-merge:" in capsys.readouterr().err

def test_convert_succeeds_after_merge(tmp_path):
    left, right = _write_two_csvs(tmp_path)
    dest = tmp_path / "merged.parquet"

    exit_code = cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-merge", "left=df1,right=df2,on=col a:cola",
        "-convert", "-o", str(dest),
    ])

    assert exit_code == 0
    assert dest.exists()
    result = pd.read_parquet(dest)
    assert list(result.columns) == ["col a", "val_l", "cola", "val_r"]
    assert len(result) == 2

def test_file_nonexistent_path_errors(tmp_path, capsys):
    a, _, _ = _write_three_id_csvs(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{a}=a;{tmp_path / 'missing.csv'}=b", "-concat", "frames='a,b'"])
    assert exc_info.value.code == 2
    assert "file not found" in capsys.readouterr().err

def test_file_bad_encoding_errors(tmp_path, capsys):
    bad_path = tmp_path / "bad.csv"
    bad_path.write_bytes("id,name\n1,caf\xe9\n".encode("latin-1"))
    ok_path = tmp_path / "ok.csv"
    pd.DataFrame({"id": [2], "name": ["bravo"]}).to_csv(ok_path, index=False)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["-file", f"{bad_path}=a;{ok_path}=b", "-concat", "frames='a,b'"])
    assert exc_info.value.code == 2
    assert "try -encoding" in capsys.readouterr().err


def test_concat_unquoted_frames(tmp_path, capsys):
    a, b, c = _write_three_id_csvs(tmp_path)

    # unquoted frames=a,b,c without inner quotes
    exit_code = cli.main(["-file", f"{a}=a;{b}=b;{c}=c", "-concat", "frames=a,b,c", "-shape"])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(8, 4)"


def test_merge_unquoted_on_pairs(tmp_path, capsys):
    left = tmp_path / "l.csv"
    right = tmp_path / "r.csv"
    pd.DataFrame({"id": [1, 2], "code": ["x", "y"], "v1": [10, 20]}).to_csv(left, index=False)
    pd.DataFrame({"id": [1, 2], "code": ["x", "y"], "v2": [100, 200]}).to_csv(right, index=False)

    exit_code = cli.main([
        "-file", f"{left}=df1;{right}=df2",
        "-merge", "left=df1,right=df2,on=id:id,code:code",
        "-shape",
    ])
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "(2, 4)"



