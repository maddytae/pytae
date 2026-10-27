# Standalone Binary Distribution (Zero-Python Portable Executables)

`pytae` can be distributed and executed as a **single-file, zero-dependency standalone binary** for Windows, macOS, and Linux.

Users do **not** need to install Python, `pip`, `uv`, C++ runtimes, or any external libraries.

---

## Why Standalone Binaries?

### 1. Zero Setup for End Users
Anyone can download the executable and immediately run high-performance data transformations, filters, aggregations, SQL queries, or the interactive REPL with zero environment configuration.

### 2. Perfect for Locked-Down Corporate Environments
In enterprise, government, finance, and healthcare IT settings:
* **No Administrator Rights**: The binary is portable. It does not write to `C:\Program Files` or system directories; it runs directly out of any user folder (e.g. `C:\Users\<username>\tools\`).
* **Bypasses Proxy & SSL Firewall Roadblocks**: Tools like Zscaler or corporate web gateways frequently break `pip install` with `SSL: CERTIFICATE_VERIFY_FAILED`. Standalone binaries contain the entire Polars engine, PyArrow, and runtime baked inside—requiring **zero network access** to run.
* **No Python Version Incompatibilities**: Never worry about outdated system Pythons (e.g. Python 3.8 on legacy enterprise laptops).
* **Automatic User-Space Persistence**: Session metadata and disk-backed Arrow IPC checkpoints are automatically saved inside the user's home folder (`~/.pytae/sessions/`), where users always have full read/write permissions.

---

## Download & Run

Download the pre-compiled binary for your operating system from the [Releases](https://github.com/maddytae/pytae/releases) page:

| OS | Architecture | Binary File |
|---|---|---|
| **Windows** | x86_64 (64-bit) | `pytae-windows-x64.zip` (Pre-extracted fast folder bundle) |
| **macOS** | Apple Silicon (M1/M2/M3/M4) | `pytae-macos-arm64` |
| **macOS** | Intel x86_64 | `pytae-macos-x86_64` |
| **Linux** | x86_64 (64-bit) | `pytae-linux-x86_64` |

### Running on Windows
1. Download and unzip `pytae-windows-x64.zip` into your user folder (e.g. `C:\Users\<username>\tools\pytae\`).
2. Add `C:\Users\<username>\tools\pytae` to your user `PATH` (no Administrator rights required).
3. Run `pytae` in any Command Prompt or PowerShell window with **instant (~150ms) startup**:
```powershell
# Quick query on a dataset
pytae sales.parquet -filter "revenue > 1000" -shape

# Launch the interactive REPL workbench
pytae
```

### Running on macOS / Linux
Open Terminal:
```bash
# Make executable
chmod +x pytae-macos-arm64

# (Optional) Move to system PATH
mv pytae-macos-arm64 /usr/local/bin/pytae

# Run
pytae sample:penguins -filter "species == 'Gentoo'" -shape
```

---

## Building Locally

To package a standalone executable on your own machine:

```bash
# Using uv (fastest):
uv run --with pyinstaller python scripts/build_binary.py

# Or using standard pip:
pip install pyinstaller
python scripts/build_binary.py
```

### Build Options

```bash
# Build standard 'pytae' (or 'pytae.exe' on Windows)
python scripts/build_binary.py

# Build with platform-tagged release name (e.g., pytae-windows-x64.exe, pytae-macos-arm64)
python scripts/build_binary.py --release-name

# Build with a custom output name
python scripts/build_binary.py --output-name my_custom_pytae
```

The compiled binary will be placed in the `dist/` folder.

---

## Automated Multi-Platform CI/CD Pipeline

The repository includes a GitHub Actions workflow at [`.github/workflows/build_binaries.yml`](file:///.github/workflows/build_binaries.yml):

1. **Matrix Build**: Concurrently builds on `ubuntu-latest`, `macos-14` (Apple Silicon), `macos-13` (Intel), and `windows-latest`.
2. **Automated Smoke Tests**: Runs automated validation tests on each compiled binary to verify that Polars, sample datasets, filters, and sessions execute properly without errors.
3. **Automated Release Publishing**: Whenever a git tag (e.g., `v3.12.6`) is pushed, the workflow automatically attaches all four standalone binaries as downloadable assets to the GitHub Release.
4. **Manual Dispatch**: Can be manually triggered at any time from the GitHub Actions tab via **Workflow Dispatch**.
