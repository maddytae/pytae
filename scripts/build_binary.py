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


def build(
    output_name: str | None = None,
    is_release: bool = False,
    strip: bool = True,
    onedir: bool = False,
    create_zip: bool = False,
) -> Path:
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
        final_stem = Path(output_name).stem
        final_name = f"{final_stem}{exe_suffix}"
    elif is_release:
        final_stem = f"pytae-{tag}"
        final_name = f"{final_stem}{exe_suffix}"
    else:
        final_stem = "pytae"
        final_name = f"pytae{exe_suffix}"

    # Separator for PyInstaller --add-data: ';' on Windows, ':' on Unix
    sep = os.pathsep
    add_data_arg = f"{datasets_dir}{sep}pytae/datasets"

    mode_arg = "--onedir" if onedir else "--onefile"

    pyinstaller_args = [
        str(cli_entry),
        "--name",
        final_stem,
        mode_arg,
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

    if is_windows:
        try:
            import pyreadline3  # noqa: F401
            pyinstaller_args.extend(["--collect-all", "pyreadline3"])
        except ImportError:
            pass

    # Apply symbol stripping on Unix to reduce binary footprint
    if strip and not is_windows:
        pyinstaller_args.append("--strip")

    print(f"Building standalone pytae ({mode_arg}) for [{tag}]...")
    if onedir:
        print(f"Output target folder: dist/{final_stem}/")
    else:
        print(f"Output target file: dist/{final_name}")

    try:
        import PyInstaller.__main__  # noqa: F401
    except ImportError:
        print("ERROR: PyInstaller is not installed. Install it with:")
        print("  pip install pyinstaller   (or: uv pip install pyinstaller)")
        sys.exit(1)

    import PyInstaller.__main__

    PyInstaller.__main__.run(pyinstaller_args)

    if onedir:
        built_dir = repo_root / "dist" / final_stem
        exe_inside = built_dir / final_name
        if not built_dir.exists() or not exe_inside.exists():
            print(f"ERROR: Expected directory bundle not found at {built_dir}")
            sys.exit(1)

        total_bytes = sum(f.stat().st_size for f in built_dir.rglob("*") if f.is_file())
        size_mb = total_bytes / (1024 * 1024)

        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL (ONEDIR BUNDLE)!")
        print(f"Directory: {built_dir}")
        print(f"Executable: {exe_inside}")
        print(f"Total bundle size: {size_mb:.1f} MB")

        if create_zip:
            zip_base = repo_root / "dist" / final_stem
            print(f"Creating zip archive: {zip_base}.zip ...")
            zip_path = shutil.make_archive(str(zip_base), "zip", root_dir=str(repo_root / "dist"), base_dir=final_stem)
            zip_mb = Path(zip_path).stat().st_size / (1024 * 1024)
            print(f"Zip created: {zip_path} ({zip_mb:.1f} MB)")
            print("=" * 60)
            return Path(zip_path)

        print("=" * 60)
        return built_dir
    else:
        built_file = repo_root / "dist" / final_name
        default_built_file = repo_root / "dist" / (final_stem + exe_suffix)

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
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Build as a pre-extracted folder bundle for instant startup on Windows",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Archive the onedir folder into a .zip file (used with --onedir)",
    )
    parser.add_argument("--no-strip", action="store_true", help="Do not strip binary symbols")
    args = parser.parse_args()

    build(
        output_name=args.output_name,
        is_release=args.release_name,
        strip=not args.no_strip,
        onedir=args.onedir,
        create_zip=args.zip,
    )


if __name__ == "__main__":
    main()
