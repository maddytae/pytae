"""Tests for REPL session variables and parameters (@var)."""

from __future__ import annotations

from pathlib import Path

from pytae.repl import PytaeRepl


def test_repl_variable_scalar_assignment():
    outputs: list[str] = []
    r = PytaeRepl()

    r.execute_line("min_mass = 3500", output_fn=outputs.append)
    assert "Set @min_mass = 3500" in outputs[-1]
    assert r.variables["min_mass"] == 3500

    r.execute_line("factor = 1.25", output_fn=outputs.append)
    assert r.variables["factor"] == 1.25

    r.execute_line('label = "Gentoo"', output_fn=outputs.append)
    assert r.variables["label"] == "Gentoo"

    r.execute_line("flag = True", output_fn=outputs.append)
    assert r.variables["flag"] is True

    r.execute_line("empty = None", output_fn=outputs.append)
    assert r.variables["empty"] is None


def test_repl_variable_at_prefix_rejected():
    outputs: list[str] = []
    r = PytaeRepl()

    # Attempting to define a variable with @ prefix is strictly rejected
    r.execute_line("@min_spend = 50.0", output_fn=outputs.append)
    assert any("session variables must be defined without '@'" in o for o in outputs)
    assert any("use 'min_spend = ...'" in o for o in outputs)
    assert "min_spend" not in r.variables
    assert "@min_spend" not in r.variables

    # Standard definition succeeds
    outputs.clear()
    r.execute_line("min_spend = 50.0", output_fn=outputs.append)
    assert "Set @min_spend = 50.0" in outputs[-1]
    assert r.variables["min_spend"] == 50.0


def test_repl_variable_collection_assignment():
    outputs: list[str] = []
    r = PytaeRepl()

    r.execute_line("species = ['Gentoo', 'Adelie']", output_fn=outputs.append)
    assert r.variables["species"] == ["Gentoo", "Adelie"]

    r.execute_line("cfg = {'min_mass': 3200, 'island': 'Torgersen', 'nested': {'n': 42}}", output_fn=outputs.append)
    assert r.variables["cfg"]["min_mass"] == 3200
    assert r.variables["cfg"]["nested"]["n"] == 42


def test_repl_bare_variable_inspection():
    outputs: list[str] = []
    r = PytaeRepl()

    r.execute_line("min_mass = 3500", output_fn=outputs.append)
    r.execute_line("species = ['Gentoo', 'Adelie']", output_fn=outputs.append)
    r.execute_line("cfg = {'island': 'Biscoe', 'scores': [10, 20]}", output_fn=outputs.append)

    outputs.clear()
    r.execute_line("@min_mass", output_fn=outputs.append)
    assert "@min_mass = 3500 (int)" in outputs[0]

    outputs.clear()
    r.execute_line("@species[0]", output_fn=outputs.append)
    assert "@species[0] = 'Gentoo' (str)" in outputs[0]

    outputs.clear()
    r.execute_line("@cfg.island", output_fn=outputs.append)
    assert "@cfg.island = 'Biscoe' (str)" in outputs[0]

    outputs.clear()
    r.execute_line("@cfg['island']", output_fn=outputs.append)
    assert "@cfg['island'] = 'Biscoe' (str)" in outputs[0]

    outputs.clear()
    r.execute_line("@cfg.scores[1]", output_fn=outputs.append)
    assert "@cfg.scores[1] = 20 (int)" in outputs[0]

    outputs.clear()
    r.execute_line("@not_found", output_fn=outputs.append)
    assert "variable '@not_found' is not defined" in outputs[0]


def test_repl_pipeline_with_variables():
    outputs: list[str] = []
    r = PytaeRepl()
    r.execute_line("df = sample:penguins", output_fn=outputs.append)
    assert r.current_df is not None

    r.execute_line("min_mass = 5000", output_fn=outputs.append)
    outputs.clear()
    # Preview filter doesn't mutate table
    r.execute_line('-filter "body_mass_g > @min_mass"', output_fn=outputs.append)
    assert r.current_df.shape[0] == 344
    assert any("Gentoo" in o for o in outputs)

    # Assigned filter mutates table
    outputs.clear()
    r.execute_line('df = -filter "body_mass_g > @min_mass"', output_fn=outputs.append)
    assert r.current_df.shape[0] == 61
    assert (r.current_df["body_mass_g"] > 5000).all()

    # List membership with variable
    r.execute_line("target_species = ['Gentoo']", output_fn=outputs.append)
    r.execute_line('df = -filter "species in @target_species"', output_fn=outputs.append)
    assert (r.current_df["species"] == "Gentoo").all()

    # Mutate with variable
    r.execute_line("factor = 1000", output_fn=outputs.append)
    r.execute_line('df = -mutate "kg = body_mass_g / @factor"', output_fn=outputs.append)
    assert "kg" in r.current_df.columns
    assert (r.current_df["kg"] > 5.0).all()


def test_repl_pipeline_with_nested_dict_variable():
    outputs: list[str] = []
    r = PytaeRepl()
    r.execute_line("df = sample:penguins", output_fn=outputs.append)

    r.execute_line("cfg = {'min_m': 4500, 'island': 'Biscoe'}", output_fn=outputs.append)
    outputs.clear()
    r.execute_line('df = -filter "body_mass_g > @cfg.min_m and island == @cfg[\'island\']"', output_fn=outputs.append)
    assert r.current_df.shape[0] > 0
    assert (r.current_df["body_mass_g"] > 4500).all()
    assert (r.current_df["island"] == "Biscoe").all()


def test_repl_sql_with_variables():
    outputs: list[str] = []
    r = PytaeRepl()
    r.execute_line("df = sample:penguins", output_fn=outputs.append)
    r.execute_line("threshold = 5500", output_fn=outputs.append)

    outputs.clear()
    r.execute_line('-sql "SELECT species, body_mass_g FROM df WHERE body_mass_g > @threshold"', output_fn=outputs.append)
    assert r.current_df is not None
    assert r.current_df.shape[0] == 28
    assert (r.current_df["body_mass_g"] > 5500).all()

    # SQL assignment with variables
    outputs.clear()
    r.execute_line('heavy = -sql "SELECT * FROM df WHERE body_mass_g > @threshold"', output_fn=outputs.append)
    assert "heavy" in r.tables
    assert r.tables["heavy"].shape[0] == 28


def test_repl_status_vars_and_rm_var():
    outputs: list[str] = []
    r = PytaeRepl()
    r.execute_line("a = 10", output_fn=outputs.append)
    r.execute_line("b = 'test'", output_fn=outputs.append)
    r.execute_line("c = [1, 2, 3]", output_fn=outputs.append)

    # status vars is rejected (no plurals under the hood)
    outputs.clear()
    r.execute_line("status vars", output_fn=outputs.append)
    assert "plural 'vars' is not recognized; use 'status var' instead" in outputs[-1]

    # status var lists all session variables
    outputs.clear()
    r.execute_line("status var", output_fn=outputs.append)
    out_text = "\n".join(outputs)
    assert "@a" in out_text
    assert "@b" in out_text
    assert "@c" in out_text

    # status var <name>
    outputs.clear()
    r.execute_line("status var a", output_fn=outputs.append)
    st_var_text = "\n".join(outputs)
    assert "@a" in st_var_text
    assert "10" in st_var_text

    # status var -v
    outputs.clear()
    r.execute_line("status var -v", output_fn=outputs.append)
    out_v = "\n".join(outputs)
    assert '"a": 10' in out_v

    # rm var a
    outputs.clear()
    r.execute_line("rm var a", output_fn=outputs.append)
    assert "Removed variable '@a'" in outputs[0]
    assert "a" not in r.variables

    # rm var *
    outputs.clear()
    r.execute_line("rm var *", output_fn=outputs.append)
    assert "Removed all session variables (2 removed)." in outputs[0]
    assert len(r.variables) == 0


def test_repl_checkpoint_and_restore_variables(tmp_path: Path):
    outputs: list[str] = []
    r = PytaeRepl(sessions_dir=tmp_path / "sessions")
    r.execute_line("df = sample:penguins", output_fn=outputs.append)
    r.execute_line("min_mass = 4200", output_fn=outputs.append)
    r.execute_line("cfg = {'env': 'prod', 'limit': 100}", output_fn=outputs.append)

    outputs.clear()
    r.execute_line("checkpoint cp1", output_fn=outputs.append)
    assert "cp1" in r.checkpoints
    assert any("2 variables: @min_mass, @cfg" in o for o in outputs)

    # Modify / delete variables
    r.execute_line("rm var *", output_fn=outputs.append)
    assert len(r.variables) == 0

    # Restore checkpoint cp1
    outputs.clear()
    r.execute_line("restore cp1", output_fn=outputs.append)
    assert any("2 variables: @min_mass, @cfg" in o for o in outputs)
    assert r.variables["min_mass"] == 4200
    assert r.variables["cfg"]["env"] == "prod"


def test_repl_namespace_isolation():
    outputs: list[str] = []
    r = PytaeRepl()

    # Reserved commands/verbs cannot be variables
    r.execute_line("filter = 10", output_fn=outputs.append)
    assert "reserved command or verb" in outputs[-1]
    assert "filter" not in r.variables

    r.execute_line("checkpoint = 5", output_fn=outputs.append)
    assert "reserved command or verb" in outputs[-1]
    assert "checkpoint" not in r.variables

    # Variable cannot overwrite active table
    r.execute_line("df = sample:penguins", output_fn=outputs.append)
    assert "df" in r.tables
    outputs.clear()
    r.execute_line("df = 123", output_fn=outputs.append)
    assert "already an active table" in outputs[-1]
    assert "df" not in r.variables

    # Table cannot overwrite active variable
    r.execute_line("my_var = 50", output_fn=outputs.append)
    assert "my_var" in r.variables
    outputs.clear()
    r.execute_line("my_var = sample:tips", output_fn=outputs.append)
    assert "already a session variable" in outputs[-1]
    assert "my_var" not in r.tables

    # Rename cannot collide with variable
    outputs.clear()
    r.execute_line("rename df my_var", output_fn=outputs.append)
    assert "already a session variable" in outputs[-1]


def test_repl_variable_autocompletion():
    r = PytaeRepl()
    r.variables["min_mass"] = 3500
    r.variables["max_mass"] = 6000
    r.variables["cfg"] = {"a": 1}

    # @var completion
    matches = r._get_completions("@m")
    assert "@min_mass" in matches
    assert "@max_mass" in matches
    assert "@cfg" not in matches

    # rm var completion
    rm_opts = r._get_completions("m", line_buf="rm var ")
    assert "min_mass" in rm_opts
    assert "max_mass" in rm_opts

    # status var completion
    st_opts = r._get_completions("c", line_buf="status var ")
    assert "cfg" in st_opts


def test_repl_status_checkpoint_and_session_display_variables(tmp_path: Path):
    from pytae.repl import set_sessions_dir

    sess_container = tmp_path / "sessions"
    sess_container.mkdir(parents=True, exist_ok=True)
    set_sessions_dir(sess_container)

    try:
        r = PytaeRepl()
        r.execute_line("df = sample:penguins")
        r.execute_line("min_mass = 3500")
        r.execute_line('project_tag = "q4_audit"')
        r.execute_line("set save_session = audit_sess")
        r.execute_line("checkpoint cp1")

        # 1. status checkpoint: Checkpoint line has container info, NOT rows x cols in front of cp1
        outputs: list[str] = []
        r.execute_line("status checkpoint", output_fn=outputs.append)
        cp_out = "\n".join(outputs)

        # Checkpoint header line does NOT have "344 rows x 7 cols" in front of cp1
        cp_header = [line for line in outputs if "cp1" in line][0]
        assert "1 table [df]" in cp_header
        assert "2 vars" in cp_header
        assert "344 rows x 7 cols" not in cp_header

        # Indented tables under cp1 show dimensions
        assert "df: 344 rows x 7 cols" in cp_out
        # Indented variables under cp1 show variable details
        assert "@min_mass: 3500 (int)" in cp_out
        assert "@project_tag: 'q4_audit' (str)" in cp_out

        # 2. status checkpoint cp1: specific checkpoint status shows tables and variables
        outputs.clear()
        r.execute_line("status checkpoint cp1", output_fn=outputs.append)
        single_cp_out = "\n".join(outputs)
        assert "Checkpoint     : cp1" in single_cp_out
        assert "Tables (1):" in single_cp_out
        assert "df            : 344 rows x 7 cols" in single_cp_out
        assert "Variables (2):" in single_cp_out
        assert "@min_mass" in single_cp_out and "3500" in single_cp_out
        assert "@project_tag" in single_cp_out and "'q4_audit'" in single_cp_out

        # 3. status session: active session status shows variables
        outputs.clear()
        r.execute_line("status session", output_fn=outputs.append)
        sess_out = "\n".join(outputs)
        assert "Variables     : 2 defined [@min_mass, @project_tag]" in sess_out

        # status session -v: verbose active session lists each variable
        outputs.clear()
        r.execute_line("status session -v", output_fn=outputs.append)
        sess_v_out = "\n".join(outputs)
        assert "@min_mass" in sess_v_out and "3500" in sess_v_out
        assert "@project_tag" in sess_v_out and "'q4_audit'" in sess_v_out

        # 4. In-memory checkpoint stores variables cleanly
        assert r.checkpoints["cp1"]["variables"] == {"min_mass": 3500, "project_tag": "q4_audit"}
        r.close()

        # 5. Status session audit_sess outputs retirement notice
        r2 = PytaeRepl()
        outputs.clear()
        r2.execute_line("status session audit_sess", output_fn=outputs.append)
        ext_sess_out = "\n".join(outputs)
        assert "persistent disk sessions have been retired" in ext_sess_out
        r2.close()
    finally:
        set_sessions_dir(None)

