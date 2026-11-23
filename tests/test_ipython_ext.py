"""End-to-end tests for Pytae's IPython integration (auto-activated on `import pytae as pt`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from IPython.core.interactiveshell import InteractiveShell

import pytae as pt
from pytae.cli import main as cli_main
from pytae.ipython_ext import register_ipython_workbench, unregister_ipython_workbench


@pytest.fixture
def ip_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> InteractiveShell:
    monkeypatch.setenv("PYTAE_HOME", str(tmp_path))
    shell = InteractiveShell()
    register_ipython_workbench(shell)
    yield shell
    unregister_ipython_workbench(shell)


def test_auto_register_on_import_and_opt_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTAE_HOME", str(tmp_path))
    shell = InteractiveShell.instance()
    try:
        unregister_ipython_workbench(shell)
        assert not hasattr(shell, "_pytae_workbench")

        # Opt-out via env var skips registration
        monkeypatch.setenv("PYTAE_NO_IPYTHON_EXT", "1")
        pt._auto_register_ipython()
        assert not hasattr(shell, "_pytae_workbench")

        # Without opt-out, auto-registers cleanly on import
        monkeypatch.delenv("PYTAE_NO_IPYTHON_EXT", raising=False)
        pt._auto_register_ipython()
        assert hasattr(shell, "_pytae_workbench")
    finally:
        unregister_ipython_workbench(shell)
        InteractiveShell.clear_instance()


def test_immutable_pt_magic(ip_shell: InteractiveShell) -> None:
    ip_shell.run_cell("import pytae as pt\ndf = pt.DataFrame({'a': [1, 2, 3, 4], 'b': [10, 20, 30, 40]})")
    res = ip_shell.run_cell('sub = %pt df -filter "a >= 3" -mutate "c = b * 2"')
    assert res.error_in_exec is None
    assert ip_shell.user_ns["df"].shape == (4, 2)  # immutable!
    assert ip_shell.user_ns["sub"].shape == (2, 3)
    assert ip_shell.user_ns["sub"]._df["c"].to_list() == [60, 80]


def test_cell_magic_pt_assigns_target(ip_shell: InteractiveShell) -> None:
    ip_shell.run_cell("import pytae as pt\ndf = pt.DataFrame({'g': ['x', 'x', 'y'], 'v': [1, 2, 10]})")
    cell = '%%pt grouped\ndf\n-by g\n-agg "s = sum(v)"\n-arrange "g"\n'
    res = ip_shell.run_cell(cell)
    assert res.error_in_exec is None
    assert "grouped" in ip_shell.user_ns
    assert ip_shell.user_ns["grouped"]._df["s"].to_list() == [3, 10]


def test_checkpoint_strict_restore_and_free_scrubs_out_cache(
    ip_shell: InteractiveShell, capsys: pytest.CaptureFixture[str]
) -> None:
    ip_shell.run_cell("import pytae as pt\ndf = pt.DataFrame({'x': [1, 2, 3]})")
    ip_shell.run_cell("df")
    assert any(isinstance(v, pt.DataFrame) for v in ip_shell.user_ns["Out"].values())

    ip_shell.run_cell("%checkpoint c1")
    # Selective checkpoint arguments are rejected
    bad_cp = ip_shell.run_cell("%checkpoint c2 df")
    assert bad_cp.error_in_exec is not None

    ip_shell.run_cell("df = df.filter('x > 1')\ntemp_df = pt.DataFrame({'z': [9]})\ntemp_var = 123")
    assert "temp_df" in ip_shell.user_ns
    assert "temp_var" in ip_shell.user_ns

    ip_shell.run_cell("%restore c1")
    assert "temp_df" not in ip_shell.user_ns
    assert "temp_var" not in ip_shell.user_ns
    assert ip_shell.user_ns["df"].shape == (3, 1)

    ip_shell.run_cell("df")
    capsys.readouterr()
    ip_shell.run_cell("%free df")
    out = capsys.readouterr().out
    assert "Freed df" in out
    assert "df" not in ip_shell.user_ns
    assert not any(isinstance(v, pt.DataFrame) for v in ip_shell.user_ns["Out"].values())


def test_status_and_set_display_persistence(
    ip_shell: InteractiveShell, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ip_shell.run_cell("import pytae as pt\ndf = pt.DataFrame({'a': [1.23456, 2.34567]})")
    capsys.readouterr()
    ip_shell.run_cell("%status")
    status_out = capsys.readouterr().out
    assert "Pytae Workbench Status" in status_out
    assert "df" in status_out

    ip_shell.run_cell("%set max_rows=5 float_precision=2 comma=true")
    ip_shell.run_cell("%set save")
    cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert cfg["max_rows"] == 5
    assert cfg["float_precision"] == 2
    assert cfg["comma"] is True


def test_export_and_exit_save(ip_shell: InteractiveShell, tmp_path: Path) -> None:
    ip_shell.run_cell("import pytae as pt\ndf = pt.DataFrame({'a': [1, 2, 3]})", store_history=True)
    ip_shell.run_cell("%checkpoint base", store_history=True)
    ip_shell.run_cell("df = df.filter('a > 100')", store_history=True)
    ip_shell.run_cell("%restore base", store_history=True)
    ip_shell.run_cell("final_df = df.filter('a >= 2')", store_history=True)

    out_py = tmp_path / "out.py"
    ip_shell.run_cell(f"%export {out_py}", store_history=True)
    content = out_py.read_text(encoding="utf-8")
    assert "final_df = df.filter('a >= 2')" in content
    assert "a > 100" not in content

    out_nb = tmp_path / "out.ipynb"
    ip_shell.run_cell(f"%export {out_nb}", store_history=True)
    nb = json.loads(out_nb.read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4
    assert len(nb["cells"]) >= 2


def test_export_prunes_errors_previews_bare_exit_and_produces_valid_python(
    ip_shell: InteractiveShell, tmp_path: Path
) -> None:
    ip_shell.run_cell("import pytae as pt", store_history=True)
    ip_shell.run_cell("%theme", store_history=True)  # errored magic
    ip_shell.run_cell("df = %pt sample:penguins", store_history=True)
    ip_shell.run_cell("df", store_history=True)  # bare inspection
    ip_shell.run_cell("df.head()", store_history=True)  # unassigned preview
    ip_shell.run_cell("%pt -head", store_history=True)  # errored %pt
    ip_shell.run_cell("%pt df -head", store_history=True)  # read-only preview
    ip_shell.run_cell('heavy = %pt df -filter "body_mass_g > 5000"', store_history=True)

    out_py = tmp_path / "maddy.py"
    ip_shell.run_cell(f"%exit -s {out_py}", store_history=True)

    text = out_py.read_text(encoding="utf-8")
    assert "%theme" not in text
    assert "%pt -head" not in text
    assert "%pt df -head" not in text
    assert "exit -s" not in text
    assert "\ndf\n" not in text
    assert "df.head()" not in text
    assert "df = pt.sample('penguins')" in text
    assert "heavy = df.filter('body_mass_g > 5000')" in text

    # Exported .py must be 100% valid, runnable standalone Python!
    exec_ns: dict[str, object] = {}
    exec(compile(text, str(out_py), "exec"), exec_ns)
    assert isinstance(exec_ns["df"], pt.DataFrame)
    assert isinstance(exec_ns["heavy"], pt.DataFrame)
    assert exec_ns["heavy"].shape[0] > 0


def test_cli_disallows_retired_repl_and_pt_flags(capsys: pytest.CaptureFixture[str]) -> None:
    for retired_argv in (["-i"], ["repl"], ["-run", "a.pt"], ["script.pt"]):
        with pytest.raises(SystemExit) as exc:
            cli_main(retired_argv)
        assert exc.value.code != 0
        err = capsys.readouterr().err
        assert "retired" in err.lower()

    with pytest.raises(SystemExit) as exc:
        cli_main(["-export", "-o", "out.py"])
    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "-history" in err

    with pytest.raises(SystemExit) as exc:
        cli_main(["-load", "script.py"])
    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "before '-load'" in err


def test_load_bootstrap_populates_ipython_history_and_vars(
    ip_shell: InteractiveShell, tmp_path: Path
) -> None:
    from pytae.workbench import run_cli_load

    script = tmp_path / "demo.py"
    script.write_text(
        "import pytae as pt\n\ndf = pt.DataFrame({'a': [1, 2, 3]})\n\nres = df.filter('a >= 2')\n",
        encoding="utf-8",
    )

    bootstraps: list[str] = []
    rc = run_cli_load(
        str(script),
        output_fn=lambda _m: None,
        launcher_fn=lambda p: (bootstraps.append(p.read_text(encoding="utf-8")), 0)[1],
    )
    assert rc == 0
    assert len(bootstraps) == 1

    # Execute the bootstrap inside a real IPython shell (just like `ipython -i <bootstrap.py>`)
    ip_shell.run_cell(bootstraps[0], store_history=False)

    # Variables are live in user_ns AND every loaded cell is recorded in In / %history
    assert "res" in ip_shell.user_ns
    assert ip_shell.user_ns["res"].shape == (2, 1)
    in_hist = ip_shell.user_ns["In"]
    assert any("import pytae as pt" in cell for cell in in_hist)
    assert any("df = pt.DataFrame" in cell for cell in in_hist)
    assert any("res = df.filter('a >= 2')" in cell for cell in in_hist)
    assert "_pytae_cells" not in ip_shell.user_ns


def test_pt_sql_cell_magic_and_export(ip_shell: InteractiveShell, tmp_path: Path) -> None:
    ip_shell.run_cell(
        "import pytae as pt\n"
        "orders = pt.DataFrame({'id': [1, 2, 3], 'cust_id': [10, 20, 10], 'amt': [50, 200, 150]})\n"
        "customers = pt.DataFrame({'id': [10, 20], 'name': ['Alice', 'Bob']})\n"
        "min_amt = 100",
        store_history=True,
    )
    sql_cell = (
        "%%pt big_orders -sql\n"
        "SELECT c.name, SUM(o.amt) AS total\n"
        "FROM orders o\n"
        "JOIN customers c ON o.cust_id = c.id\n"
        "WHERE o.amt >= @min_amt\n"
        "GROUP BY c.name\n"
        "ORDER BY total DESC\n"
    )
    res = ip_shell.run_cell(sql_cell, store_history=True)
    assert res.error_in_exec is None
    assert "big_orders" in ip_shell.user_ns
    out_df = ip_shell.user_ns["big_orders"]
    assert out_df._df["name"].to_list() == ["Bob", "Alice"]
    assert out_df._df["total"].to_list() == [200, 150]

    # Export produces valid runnable standalone Python
    out_py = tmp_path / "sql_export.py"
    ip_shell.run_cell(f"%export {out_py}", store_history=True)
    text = out_py.read_text(encoding="utf-8")
    assert "big_orders = pt.eval_cli(" in text
    exec_ns: dict[str, object] = {}
    exec(compile(text, str(out_py), "exec"), exec_ns)
    assert exec_ns["big_orders"]._df["total"].to_list() == [200, 150]


def test_pt_doc_and_in_memory_join_concat(
    ip_shell: InteractiveShell, capsys: pytest.CaptureFixture[str]
) -> None:
    ip_shell.run_cell(
        "import pytae as pt\n"
        "df1 = pt.DataFrame({'id': [1, 2, 3], 'val': [10, 20, 30]})\n"
        "df2 = pt.DataFrame({'id': [2, 3], 'tag': ['B', 'C']})"
    )

    # 1. In-process doc search via `%pt -doc`
    capsys.readouterr()
    res_doc = ip_shell.run_cell("%pt -doc explode")
    assert res_doc.error_in_exec is None
    doc_out = capsys.readouterr().out
    assert "explode" in doc_out.lower()

    # 2. Direct in-memory join (`%pt df1 -join "right=df2, on=id"`)
    res_j1 = ip_shell.run_cell('j1 = %pt df1 -join "right=df2, on=id, how=inner"')
    assert res_j1.error_in_exec is None
    assert ip_shell.user_ns["j1"].shape == (2, 3)

    # 3. Pipeline filter BEFORE in-memory join (`%pt df1 -filter ... -join "right=df2, on=id"`)
    res_j2 = ip_shell.run_cell('j2 = %pt df1 -filter "val >= 25" -join "right=df2, on=id, how=inner"')
    assert res_j2.error_in_exec is None
    assert ip_shell.user_ns["j2"].shape == (1, 3)
    assert ip_shell.user_ns["j2"]._df["tag"].to_list() == ["C"]

    # 4. In-memory concat (`%pt a=df1 b=df1 -concat`)
    res_c = ip_shell.run_cell('stacked = %pt a=df1 b=df1 -concat "frames=a,b"')
    assert res_c.error_in_exec is None
    assert ip_shell.user_ns["stacked"].shape == (6, 2)

    # 5. In-process cheatsheet (`%pt -cheatsheet`)
    capsys.readouterr()
    res_cs = ip_shell.run_cell("%pt -cheatsheet")
    assert res_cs.error_in_exec is None
    assert "PYTAE CLI CHEAT SHEET" in capsys.readouterr().out

    # 6. `%pt df -plot ...` returns the matplotlib Figure inside IPython
    import matplotlib

    matplotlib.use("Agg")
    res_plot = ip_shell.run_cell('fig = %pt df1 -plot "kind=bar, x=id, y=val"')
    assert res_plot.error_in_exec is None
    assert "fig" in ip_shell.user_ns
    assert hasattr(ip_shell.user_ns["fig"], "savefig")


def test_free_df_vars_and_star_preserve_imports_and_functions(ip_shell: InteractiveShell) -> None:
    ip_shell.run_cell(
        "import pytae as pt\n"
        "def helper(x): return x + 1\n"
        "df1 = pt.DataFrame({'a': [1, 2]})\n"
        "df2 = pt.DataFrame({'b': [3, 4]})\n"
        "cutoff = 100\n"
        "tags = ['x', 'y']"
    )

    # 1. `%free -vars` deletes user vars only, keeps DataFrames, imports, and functions
    ip_shell.run_cell("%free -vars")
    assert "cutoff" not in ip_shell.user_ns
    assert "tags" not in ip_shell.user_ns
    assert "df1" in ip_shell.user_ns and "df2" in ip_shell.user_ns
    assert "pt" in ip_shell.user_ns and "helper" in ip_shell.user_ns

    # 2. `%free -df` deletes DataFrames only, keeps new user vars, imports, and functions
    ip_shell.run_cell("threshold = 42")
    ip_shell.run_cell("%free -df")
    assert "df1" not in ip_shell.user_ns and "df2" not in ip_shell.user_ns
    assert ip_shell.user_ns["threshold"] == 42
    assert "pt" in ip_shell.user_ns and "helper" in ip_shell.user_ns

    # 3. `%free *` deletes BOTH DataFrames and user vars, still keeps imports & functions
    ip_shell.run_cell("df3 = pt.DataFrame({'c': [5]})\nlabel = 'demo'")
    ip_shell.run_cell("%free *")
    assert "df3" not in ip_shell.user_ns
    assert "threshold" not in ip_shell.user_ns
    assert "label" not in ip_shell.user_ns
    assert "pt" in ip_shell.user_ns and "helper" in ip_shell.user_ns
