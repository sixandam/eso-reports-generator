"""
Automated Windows Installer & Portable Binary Build Script for ESO Reports Generator.
Builds:
1. Standalone frozen directory: dist/eso-reports/ (via PyInstaller)
2. Standalone portable executable: Windows/eso-reports-portable.exe (via PyInstaller)
3. Windows setup installer wizard: Windows/eso-reports-setup.exe (via Inno Setup)
"""

from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEV_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = DEV_DIR.parent
INSTALLER_DIR = DEV_DIR / "installer"
DIST_DIR = PROJECT_ROOT / "dist"
WINDOWS_DIR = PROJECT_ROOT / "Windows"
SPEC_FILE = INSTALLER_DIR / "eso-reports.spec"
ISS_FILE = INSTALLER_DIR / "installer.iss"
ICON_SCRIPT = DEV_DIR / "scripts" / "make_icon.py"
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
    """Runs PyInstaller to compile both onedir and portable onefile executables."""
    print("\n[1/2] Compiling standalone binaries and portable executable with PyInstaller...")
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
    portable_exe = DIST_DIR / "eso-reports-portable.exe"

    if not app_exe.exists():
        raise RuntimeError(f"PyInstaller build finished, but directory binary {app_exe} was not found.")
    if not portable_exe.exists():
        raise RuntimeError(f"PyInstaller build finished, but portable binary {portable_exe} was not found.")

    WINDOWS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(portable_exe, WINDOWS_DIR / "eso-reports-portable.exe")

    print(f"--> Standalone binaries compiled successfully to: {DIST_DIR / 'eso-reports'}")
    print(f"--> Standalone portable executable ready at:     {WINDOWS_DIR / 'eso-reports-portable.exe'}")


def build_inno_installer(iscc_path: Path):
    """Compiles the Windows setup executable using Inno Setup."""
    print(f"\n[2/2] Compiling Windows installer wizard using Inno Setup ({iscc_path})...")
    cmd = [str(iscc_path), str(ISS_FILE)]
    subprocess.run(cmd, check=True)

    setup_exe = DIST_DIR / "eso-reports-setup.exe"
    if not setup_exe.exists():
        raise RuntimeError(f"Inno Setup compilation finished, but {setup_exe} was not found.")

    WINDOWS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(setup_exe, WINDOWS_DIR / "eso-reports-setup.exe")


def print_summary(iscc_path: Path | None):
    """Prints a clear summary of all generated deliverables."""
    print("\n" + "=" * 76)
    print("  BUILD COMPLETE: Windows Distribution Artifacts Ready")
    print("=" * 76)

    setup_exe = WINDOWS_DIR / "eso-reports-setup.exe"
    if not setup_exe.exists():
        setup_exe = DIST_DIR / "eso-reports-setup.exe"

    portable_exe = WINDOWS_DIR / "eso-reports-portable.exe"
    if not portable_exe.exists():
        portable_exe = DIST_DIR / "eso-reports-portable.exe"

    app_dir = DIST_DIR / "eso-reports"

    if setup_exe.exists():
        size_mb = setup_exe.stat().st_size / (1024 * 1024)
        print(f"  [1] Setup Wizard:    {setup_exe}")
        print(f"      Size:            {size_mb:.2f} MB")
        print("      Description:     Standard Windows installer with Desktop & Start Menu shortcuts")
        print("                       and uninstaller in Add/Remove Programs.\n")

    if portable_exe.exists():
        size_mb = portable_exe.stat().st_size / (1024 * 1024)
        print(f"  [2] Portable Exe:    {portable_exe}")
        print(f"      Size:            {size_mb:.2f} MB")
        print("      Description:     Single-file portable executable. Runs immediately without")
        print("                       installing; can be run from Desktop or USB drive.\n")

    if app_dir.exists():
        print(f"  [3] Standalone Dir:  {app_dir}")
        print("      Description:     Unpacked application directory containing eso-reports.exe")
        print("                       and bundled runtime components.\n")

    print("=" * 76)


def main():
    print("=" * 76)
    print("  ESO Reports Generator - Windows Build Script")
    print("=" * 76)

    # 1. Icon check
    ensure_icon()

    # 2. Check for ISCC before or during build
    iscc_path = find_iscc()
    if not iscc_path:
        print("[WARNING] Inno Setup compiler (ISCC.exe) was not found in PATH or standard directories.")
        print("          The application binaries will still be compiled, but eso-reports-setup.exe")
        print("          cannot be packaged until Inno Setup is installed.")
        print("          Download Inno Setup: https://jrsoftware.org/isdl.php\n")

    # 3. PyInstaller (builds onedir + portable onefile)
    build_pyinstaller()

    # 4. Inno Setup (builds setup wizard from onedir)
    if iscc_path:
        build_inno_installer(iscc_path)

    # 5. Summary
    print_summary(iscc_path)


if __name__ == "__main__":
    main()
