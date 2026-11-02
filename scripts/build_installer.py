"""
Automated Windows Installer Build Script for Lyn-Dan Heights ESO Reports.
Builds:
1. Standalone frozen directory: dist/eso-reports/ (via PyInstaller)
2. Windows setup installer wizard: dist/eso-reports-setup.exe (via Inno Setup)
"""

from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALLER_DIR = PROJECT_ROOT / "installer"
DIST_DIR = PROJECT_ROOT / "dist"
SPEC_FILE = INSTALLER_DIR / "eso-reports.spec"
ISS_FILE = INSTALLER_DIR / "installer.iss"
ICON_SCRIPT = PROJECT_ROOT / "scripts" / "make_icon.py"
ICON_PATH = PROJECT_ROOT / "assets" / "app_icon.ico"


def find_iscc() -> Path | None:
    """Finds the Inno Setup compiler executable (ISCC.exe)."""
    # 1. Check PATH
    which_iscc = shutil.which("iscc") or shutil.which("ISCC.exe")
    if which_iscc:
        return Path(which_iscc)

    # 2. Check standard install locations
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "")

    candidates = [
        Path(local_app_data) / "Programs" / "Inno Setup 7" / "ISCC.exe",
        Path(local_app_data) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(program_files) / "Inno Setup 7" / "ISCC.exe",
        Path(program_files) / "Inno Setup 6" / "ISCC.exe",
        Path(program_files_x86) / "Inno Setup 7" / "ISCC.exe",
        Path(program_files_x86) / "Inno Setup 6" / "ISCC.exe",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


def ensure_icon():
    """Ensures that assets/app_icon.ico is present."""
    if not ICON_PATH.exists():
        print("--> Generating multi-resolution icon...")
        cmd = [sys.executable, str(ICON_SCRIPT)]
        res = subprocess.run(cmd, check=True)
        if res.returncode != 0:
            raise RuntimeError("Failed to generate application icon.")
    else:
        print(f"--> Application icon verified at {ICON_PATH}")


def build_pyinstaller():
    """Runs PyInstaller using installer/eso-reports.spec."""
    print("\n[1/2] Compiling standalone Windows application with PyInstaller...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(SPEC_FILE),
        "--clean",
        "--noconfirm",
        f"--distpath={DIST_DIR}",
        f"--workpath={PROJECT_ROOT / 'build'}",
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    app_exe = DIST_DIR / "eso-reports" / "eso-reports.exe"
    if not app_exe.exists():
        raise RuntimeError(f"PyInstaller build finished, but {app_exe} was not found.")
    print(f"--> Standalone binaries compiled successfully to: {DIST_DIR / 'eso-reports'}")


def build_inno_installer(iscc_path: Path):
    """Compiles the Windows setup executable using Inno Setup."""
    print(f"\n[2/2] Compiling Windows installer wizard using Inno Setup ({iscc_path})...")
    cmd = [str(iscc_path), str(ISS_FILE)]
    subprocess.run(cmd, check=True)

    setup_exe = DIST_DIR / "eso-reports-setup.exe"
    if not setup_exe.exists():
        raise RuntimeError(f"Inno Setup compilation finished, but {setup_exe} was not found.")

    size_mb = setup_exe.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 70)
    print("SUCCESS: Windows Installer Ready!")
    print(f"  Installer: {setup_exe}")
    print(f"  Size:      {size_mb:.2f} MB")
    print("=" * 70)


def main():
    print("=" * 70)
    print("  Lyn-Dan Heights ESO Reports - Windows Installer Build Script")
    print("=" * 70)

    # 1. Icon check
    ensure_icon()

    # 2. Check for ISCC before or during build
    iscc_path = find_iscc()
    if not iscc_path:
        print("[WARNING] Inno Setup compiler (ISCC.exe) was not found in PATH or standard directories.")
        print("          The application binaries will still be compiled, but eso-reports-setup.exe")
        print("          cannot be packaged until Inno Setup is installed.")
        print("          Download Inno Setup: https://jrsoftware.org/isdl.php\n")

    # 3. PyInstaller
    build_pyinstaller()

    # 4. Inno Setup
    if iscc_path:
        build_inno_installer(iscc_path)
    else:
        print("\n[NOTE] Standalone directory is ready in dist/eso-reports/.")
        print("To generate eso-reports-setup.exe, install Inno Setup and re-run this script.")


if __name__ == "__main__":
    main()

