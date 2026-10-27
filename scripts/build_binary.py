#!/usr/bin/env python3
"""Cross-platform standalone binary packaging script for pytae using PyInstaller.

Produces a single-file, zero-dependency executable that runs without Python:
  - Windows:  dist/pytae.exe (or dist/pytae-windows-x64.exe)
  - macOS:    dist/pytae (or dist/pytae-macos-arm64 / dist/pytae-macos-x86_64)
  - Linux:    dist/pytae (or dist/pytae-linux-x86_64)

Usage:
  python scripts/build_binary.py
  python scripts/build_binary.py --release-name
  python scripts/build_binary.py --output-name custom_pytae
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
from pathlib import Path


def get_platform_tag() -> str:
    """Return a canonical platform-arch tag (e.g., windows-x64, macos-arm64, linux-x86_64)."""
    sys_name = platform.system().lower()
    machine = platform.machine().lower()

    if sys_name == "darwin":
        os_tag = "macos"
        arch_tag = "arm64" if machine in ("arm64", "aarch64") else "x86_64"
    elif sys_name == "windows":
        os_tag = "windows"
        arch_tag = "x64" if machine in ("amd64", "x86_64") else machine
    elif sys_name == "linux":
        os_tag = "linux"
        arch_tag = "x86_64" if machine in ("x86_64", "amd64") else machine
    else:
        os_tag = sys_name
        arch_tag = machine

    return f"{os_tag}-{arch_tag}"


def build(output_name: str | None = None, is_release: bool = False, strip: bool = True) -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    src_dir = repo_root / "src"
    datasets_dir = src_dir / "pytae" / "datasets"
    cli_entry = src_dir / "pytae" / "cli.py"

    if not cli_entry.exists():
        raise FileNotFoundError(f"CLI entrypoint not found at {cli_entry}")

    tag = get_platform_tag()
    is_windows = platform.system().lower() == "windows"
    exe_suffix = ".exe" if is_windows else ""

    if output_name:
        final_name = output_name if output_name.endswith(exe_suffix) else f"{output_name}{exe_suffix}"
    elif is_release:
        final_name = f"pytae-{tag}{exe_suffix}"
    else:
        final_name = f"pytae{exe_suffix}"

    # Separator for PyInstaller --add-data: ';' on Windows, ':' on Unix
    sep = os.pathsep
    add_data_arg = f"{datasets_dir}{sep}pytae/datasets"

    pyinstaller_args = [
        str(cli_entry),
        "--name",
        Path(final_name).stem,
        "--onefile",
        "--clean",
        "--noconfirm",
        "--add-data",
        add_data_arg,
        "--collect-all",
        "polars",
        "--copy-metadata",
        "pyarrow",
        "--copy-metadata",
        "pytae",
        "--hidden-import",
        "pytae",
    ]

    try:
        import matplotlib  # noqa: F401
        pyinstaller_args.extend(["--collect-all", "matplotlib"])
    except ImportError:
        pass

    try:
        import scipy  # noqa: F401
        pyinstaller_args.extend(["--collect-all", "scipy"])
    except ImportError:
        pass

    # Apply symbol stripping on Unix to reduce binary footprint
    if strip and not is_windows:
        pyinstaller_args.append("--strip")

    print(f"Building standalone pytae binary for [{tag}]...")
    print(f"Output target: dist/{final_name}")

    try:
        import PyInstaller.__main__  # noqa: F401
    except ImportError:
        print("ERROR: PyInstaller is not installed. Install it with:")
        print("  pip install pyinstaller   (or: uv pip install pyinstaller)")
        sys.exit(1)

    import PyInstaller.__main__

    PyInstaller.__main__.run(pyinstaller_args)

    built_file = repo_root / "dist" / final_name
    default_built_file = repo_root / "dist" / (Path(final_name).stem + exe_suffix)

    if not built_file.exists() and default_built_file.exists():
        shutil.move(str(default_built_file), str(built_file))

    if built_file.exists():
        size_mb = built_file.stat().st_size / (1024 * 1024)
        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print(f"Binary path: {built_file}")
        print(f"Binary size: {size_mb:.1f} MB")
        print("=" * 60)
        return built_file
    else:
        print(f"ERROR: Expected binary not found at {built_file}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build pytae standalone binary via PyInstaller")
    parser.add_argument("--output-name", "-o", help="Custom name for the output executable")
    parser.add_argument(
        "--release-name",
        action="store_true",
        help="Use platform-tagged release name (e.g., pytae-macos-arm64, pytae-windows-x64.exe)",
    )
    parser.add_argument("--no-strip", action="store_true", help="Do not strip binary symbols")
    args = parser.parse_args()

    build(output_name=args.output_name, is_release=args.release_name, strip=not args.no_strip)


if __name__ == "__main__":
    main()
