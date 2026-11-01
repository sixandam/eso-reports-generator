# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification for ESO Suite Fire Incidents Report Generator.
Builds:
1. Portable standalone executable: dist/eso-reports-portable.exe
2. Distribution directory: dist/eso-reports/ (for Inno Setup and portable .zip)
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Asset data files
datas = [
    ('assets', 'assets'),
]
binaries = []
hiddenimports = [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtSvg',
    'openpyxl',
    'pydantic',
    'click',
    'rich',
]

# Collect all Playwright driver files (node.exe, cli, driver scripts)
p_datas, p_binaries, p_hiddenimports = collect_all('playwright')
datas += p_datas
binaries += p_binaries
hiddenimports += p_hiddenimports

a = Analysis(
    ['src/cli.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'pytest',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Target 1: Standalone single-file portable executable
exe_portable = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='eso-reports-portable',
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
    icon='assets/app_icon.ico',
)

# Target 2: Standalone folder (for Inno Setup and zip distribution)
exe_dir = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='eso-reports',
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
    icon='assets/app_icon.ico',
)

coll = COLLECT(
    exe_dir,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='eso-reports',
)

