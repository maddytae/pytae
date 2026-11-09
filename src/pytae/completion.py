"""Shell tab-completion generation and installation for pytae CLI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ZSH_COMPLETION = """#compdef pytae

_pytae() {
    local -a flags
    flags=(
        "-filter[Filter rows with expression]:conditions:"
        "-mutate[Create or transform columns]:spec:"
        "-select[Keep, rename, or drop columns]:columns:"
        "-by[Group by columns]:columns:"
        "-agg[Aggregate expressions]:aggs:"
        "-arrange[Sort rows]:order:"
        "-distinct[Deduplicate rows]:columns:"
        "-join[Join with another table]:spec:"
        "-concat[Concatenate tables]:spec:"
        "-reshape[Reshape wide or long]:spec:"
        "-explode[Unnest list/array columns]:columns:"
        "-head[Print first N rows]:limit:"
        "-tail[Print last N rows]:limit:"
        "-shape[Print table dimensions]"
        "-cols[Print column names]:order:"
        "-dtype[Print column types]:order:"
        "-glimpse[Transposed schema and preview]"
        "-freq[Frequency table for categorical columns]:column:"
        "-hist[ASCII histogram for numeric column]:column:"
        "-diff[Compare two tables]:spec:"
        "-sql[Execute SQL query]:query:"
        "-o[Output destination file (.parquet, .csv, .ipc, .xlsx) or clip]:output:_files"
        "-check[Check syntax of a script or pipeline]:script:_files"
        "-doc[Search Pytae documentation]:query:"
        "-mcp[Start Model Context Protocol server]"
        "-run[Execute a .pt pipeline script]:script:_files"
        "-export[Export REPL session history]:history:_files"
        "-i[Launch interactive REPL]"
        "-benchmark[Benchmark pipeline execution]"
        "-cheatsheet[Display cheatsheet]"
        "-version[Show version]"
        "-help[Show help]"
        "--install-completion[Install shell tab completion]"
        "--completion[Output shell tab completion script]"
    )

    _arguments -s -S "${flags[@]}" "*:file:_files"
}

if [[ -n "$ZSH_VERSION" ]]; then
    if ! typeset -f compdef >/dev/null 2>&1; then
        autoload -Uz compinit && compinit -i
    fi
    compdef _pytae pytae py pt 2>/dev/null || true

    # Aliases so running `py` or `pt` directly works as `pytae`
    alias py="pytae" 2>/dev/null || true
    alias pt="pytae" 2>/dev/null || true

    # Expand 'py' or 'pt' to 'pytae ' on TAB when typed as command
    if [[ -o interactive ]]; then
        _pytae_expand_tab() {
            if [[ "$BUFFER" =~ ^[[:space:]]*(py|pt)$ ]]; then
                BUFFER="${BUFFER%${MATCH}}pytae "
                CURSOR=${#BUFFER}
            else
                zle expand-or-complete
            fi
        }
        zle -N _pytae_expand_tab
        bindkey '^I' _pytae_expand_tab
    fi
fi
"""

BASH_COMPLETION = """_pytae_completion() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local flags="-filter -mutate -select -by -agg -arrange -distinct -join -concat -reshape -explode -head -tail -shape -cols -dtype -glimpse -freq -hist -diff -sql -o -check -doc -mcp -run -export -i -benchmark -cheatsheet -version -help --install-completion --completion"

    if [[ "${cur}" == -* ]] ; then
        COMPREPLY=( $(compgen -W "${flags}" -- "${cur}") )
        return 0
    fi

    COMPREPLY=( $(compgen -f -- "${cur}") )
}
complete -F _pytae_completion pytae py pt 2>/dev/null || complete -F _pytae_completion pytae
alias py="pytae" 2>/dev/null || true
alias pt="pytae" 2>/dev/null || true
"""

FISH_COMPLETION = """complete -c pytae -f
complete -c pytae -a '(__fish_complete_path)' -d "Tabular file"
complete -c pytae -s filter -d "Filter rows with expression"
complete -c pytae -s mutate -d "Create or transform columns"
complete -c pytae -s select -d "Keep, rename, or drop columns"
complete -c pytae -s by -d "Group by columns"
complete -c pytae -s agg -d "Aggregate expressions"
complete -c pytae -s arrange -d "Sort rows"
complete -c pytae -s distinct -d "Deduplicate rows"
complete -c pytae -s join -d "Join with another table"
complete -c pytae -s concat -d "Concatenate tables"
complete -c pytae -s reshape -d "Reshape wide or long"
complete -c pytae -s explode -d "Unnest list/array columns"
complete -c pytae -s head -d "Print first N rows"
complete -c pytae -s tail -d "Print last N rows"
complete -c pytae -s shape -d "Print table dimensions"
complete -c pytae -s cols -d "Print column names"
complete -c pytae -s dtype -d "Print column types"
complete -c pytae -s glimpse -d "Transposed schema and preview"
complete -c pytae -s freq -d "Frequency table for categorical columns"
complete -c pytae -s hist -d "ASCII histogram for numeric column"
complete -c pytae -s diff -d "Compare two tables"
complete -c pytae -s sql -d "Execute SQL query"
complete -c pytae -s o -d "Output destination file or clip"
complete -c pytae -s check -d "Check syntax of a script or pipeline"
complete -c pytae -s doc -d "Search Pytae documentation"
complete -c pytae -s mcp -d "Start Model Context Protocol server"
complete -c pytae -s run -d "Execute a .pt pipeline script"
complete -c pytae -s export -d "Export REPL session history"
complete -c pytae -s i -d "Launch interactive REPL"
complete -c pytae -s benchmark -d "Benchmark pipeline execution"
complete -c pytae -s cheatsheet -d "Display cheatsheet"
complete -c pytae -s version -d "Show version"
complete -c pytae -s help -d "Show help"
complete -c pytae -l install-completion -d "Install shell tab completion"
complete -c pytae -l completion -d "Output shell tab completion script"
alias py pytae
alias pt pytae
complete -c py -w pytae
complete -c pt -w pytae
"""


def detect_shell() -> str:
    """Detect current shell from $SHELL environment variable."""
    shell_env = os.environ.get("SHELL", "").lower()
    if "zsh" in shell_env:
        return "zsh"
    elif "fish" in shell_env:
        return "fish"
    elif "bash" in shell_env:
        return "bash"
    # Fallback by OS
    return "zsh" if sys.platform == "darwin" else "bash"


def get_completion_script(shell: str) -> str:
    """Return completion script for the given shell ('zsh', 'bash', 'fish')."""
    s = shell.lower().strip()
    if s == "zsh":
        return ZSH_COMPLETION
    elif s == "bash":
        return BASH_COMPLETION
    elif s == "fish":
        return FISH_COMPLETION
    raise ValueError(f"Unsupported shell: '{shell}'. Supported shells: zsh, bash, fish.")


def run_completion(argv: list[str]) -> int:
    """Print completion script to stdout."""
    shell = argv[0] if argv else detect_shell()
    try:
        script = get_completion_script(shell)
        sys.stdout.write(script)
        return 0
    except ValueError as e:
        sys.stderr.write(f"pytae error: {e}\n")
        return 1


def run_install_completion(argv: list[str]) -> int:
    """Install completion script into user shell config."""
    shell = argv[0] if argv else detect_shell()
    home = Path.home()
    config_dir = home / ".pytae" / "completion"
    config_dir.mkdir(parents=True, exist_ok=True)

    try:
        script = get_completion_script(shell)
    except ValueError as e:
        sys.stderr.write(f"pytae error: {e}\n")
        return 1

    if shell == "zsh":
        comp_file = config_dir / "_pytae.zsh"
        comp_file.write_text(script, encoding="utf-8")
        rc_file = home / ".zshrc"
        source_line = f'[[ -f "{comp_file}" ]] && source "{comp_file}"'
        _append_if_missing(rc_file, source_line)
        sys.stdout.write(f"✓ Installed pytae completion for zsh in {comp_file}\n")
        sys.stdout.write(f"  Added source line to {rc_file}\n")
        sys.stdout.write("  To activate now, run: source ~/.zshrc\n")
        return 0

    elif shell == "bash":
        comp_file = config_dir / "pytae.bash"
        comp_file.write_text(script, encoding="utf-8")
        rc_file = home / ".bash_profile" if (home / ".bash_profile").exists() and not (home / ".bashrc").exists() else home / ".bashrc"
        source_line = f'[[ -f "{comp_file}" ]] && source "{comp_file}"'
        _append_if_missing(rc_file, source_line)
        sys.stdout.write(f"✓ Installed pytae completion for bash in {comp_file}\n")
        sys.stdout.write(f"  Added source line to {rc_file}\n")
        sys.stdout.write(f"  To activate now, run: source {rc_file}\n")
        return 0

    elif shell == "fish":
        fish_comp_dir = home / ".config" / "fish" / "completions"
        fish_comp_dir.mkdir(parents=True, exist_ok=True)
        comp_file = fish_comp_dir / "pytae.fish"
        comp_file.write_text(script, encoding="utf-8")
        sys.stdout.write(f"✓ Installed pytae completion for fish in {comp_file}\n")
        sys.stdout.write("  Fish automatically loads completions from that directory.\n")
        return 0

    return 0


def _append_if_missing(file_path: Path, line: str) -> None:
    content = file_path.read_text(encoding="utf-8", errors="ignore") if file_path.exists() else ""
    if line not in content:
        with open(file_path, "a", encoding="utf-8") as f:
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write(f"\n# pytae shell completion\n{line}\n")


def check_first_run_hint() -> None:
    """Print a one-time subtle hint in interactive TTY if completion is not installed."""
    try:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            return
        # Don't show in test environments
        if "PYTEST_CURRENT_TEST" in os.environ or "CI" in os.environ:
            return

        home = Path.home()
        hint_file = home / ".pytae" / ".completion_hint_shown"
        comp_dir = home / ".pytae" / "completion"
        if comp_dir.exists() or hint_file.exists():
            return

        hint_file.parent.mkdir(parents=True, exist_ok=True)
        hint_file.write_text("1", encoding="utf-8")

        shell = detect_shell()
        sys.stderr.write(f"💡 Tip: Run 'pytae --install-completion' to enable tab-completion in {shell}.\n\n")
    except Exception:
        pass
