# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build specification for Lyn-Dan Heights ESO Reports.
Builds the standalone directory dist/eso-reports/ for Inno Setup packaging.
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

# PyInstaller defines SPECPATH as the directory containing this .spec file
PROJECT_ROOT = Path(SPECPATH).resolve().parent

# Collect application assets
datas = [
    (str(PROJECT_ROOT / "assets"), "assets"),
]
binaries = []
hiddenimports = [
    "eso_reports",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtSvg",
    "openpyxl",
    "pydantic",
    "pydantic_core",
    "click",
    "rich",
]

# Collect Playwright browser automation driver & bindings
p_datas, p_binaries, p_hiddenimports = collect_all("playwright")
datas += p_datas
binaries += p_binaries
hiddenimports += p_hiddenimports

a = Analysis(
    [str(PROJECT_ROOT / "installer" / "entrypoint.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "pytest",
        "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="eso-reports",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / "assets" / "app_icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="eso-reports",
)

exe_portable = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="eso-reports-portable",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / "assets" / "app_icon.ico"),
)
