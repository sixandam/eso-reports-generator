"""
Unit tests for Windows portability, path resolution, browser discovery,
and PyInstaller resource resolution.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from eso_reports import config
from eso_reports import auth


def test_app_icon_ico_exists():
    """Verifies that the multi-resolution Windows .ico file was generated and is valid."""
    assert config.ICO_PATH.exists()
    assert config.ICO_PATH.is_file()
    assert config.ICO_PATH.stat().st_size > 10000  # Multi-size ico is > 100KB


def test_get_resource_path_dev_mode():
    """In standard development mode, get_resource_path resolves relative to PROJECT_ROOT."""
    with patch.object(sys, "frozen", False, create=True):
        res = config.get_resource_path("assets/check.svg")
        assert res == config.PROJECT_ROOT / "assets/check.svg"


def test_get_resource_path_frozen_mode(tmp_path: Path):
    """In PyInstaller frozen mode, get_resource_path resolves relative to sys._MEIPASS."""
    fake_meipass = tmp_path / "_MEI123456"
    fake_meipass.mkdir()
    fake_asset = fake_meipass / "assets" / "check.svg"
    fake_asset.parent.mkdir()
    fake_asset.write_text("<svg></svg>")

    with patch.object(sys, "frozen", True, create=True):
        with patch.object(sys, "_MEIPASS", str(fake_meipass), create=True):
            res = config.get_resource_path("assets/check.svg")
            assert res == fake_meipass / "assets/check.svg"


def test_get_default_desktop_path_windows_onedrive(tmp_path: Path, monkeypatch):
    """Verifies OneDrive Desktop discovery on Windows."""
    fake_userprofile = tmp_path / "Users" / "Firefighter"
    fake_onedrive_desktop = fake_userprofile / "OneDrive" / "Desktop"
    fake_onedrive_desktop.mkdir(parents=True)

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("USERPROFILE", str(fake_userprofile))

    # Mock winreg to raise FileNotFoundError so it falls back to OneDrive candidate
    with patch.dict("sys.modules", {"winreg": None}):
        desktop = config.get_default_desktop_path()
        assert desktop == fake_onedrive_desktop


def test_find_system_browser_windows_edge(tmp_path: Path, monkeypatch):
    """Verifies standard Microsoft Edge path detection on Windows."""
    fake_edge = tmp_path / "msedge.exe"
    fake_edge.write_text("")

    monkeypatch.setattr(sys, "platform", "win32")
    with patch("eso_reports.auth.Path.is_file", return_value=True):
        browser = auth.find_system_browser()
        assert browser is not None
        assert "msedge.exe" in browser.lower()


def test_launch_browser_fallback_channel():
    """Verifies that _launch_browser falls back from msedge to chrome or unchanneled launch if channel fails."""
    mock_playwright = MagicMock()
    mock_browser = MagicMock()

    # First call with channel="msedge" fails, second call with channel="chrome" succeeds
    mock_playwright.chromium.launch.side_effect = [
        Exception("msedge not found"),
        mock_browser,
    ]

    res = auth._launch_browser(mock_playwright, {"headless": True, "channel": "msedge"})
    assert res == mock_browser
    assert mock_playwright.chromium.launch.call_count == 2


def test_spec_file_defines_both_onedir_and_portable_exe():
    """Verifies that the PyInstaller specification defines both onedir and portable targets."""
    spec_path = config.PROJECT_ROOT / "installer" / "eso-reports.spec"
    assert spec_path.exists()
    content = spec_path.read_text(encoding="utf-8")
    assert "COLLECT(" in content
    assert 'name="eso-reports-portable"' in content
    assert "exe_portable = EXE(" in content


def test_root_launch_scripts_exist():
    """Verifies consumer convenience scripts exist in repository root."""
    build_bat = config.PROJECT_ROOT / "build.bat"
    run_bat = config.PROJECT_ROOT / "run.bat"
    assert build_bat.exists()
    assert run_bat.exists()
