"""
Central configuration module for ESO Suite Fire Incidents Report Generator.
Defines application constants, cross-platform directory paths, and default settings.
Supports Linux (XDG Base Directory) and Windows (%APPDATA%, active Desktop / OneDrive).
"""

from __future__ import annotations
from datetime import date
import os
from pathlib import Path
import sys


# -----------------------------------------------------------------------------
# Cross-Platform Directory Specification & Application Paths
# -----------------------------------------------------------------------------
APP_NAME = "eso-reports"

# Base configuration & state directories
if sys.platform == "win32":
    _appdata = os.environ.get("APPDATA")
    APP_CONFIG_DIR = Path(_appdata) / APP_NAME if _appdata else Path.home() / "AppData" / "Roaming" / APP_NAME
    _localappdata = os.environ.get("LOCALAPPDATA", _appdata)
    APP_STATE_DIR = Path(_localappdata) / APP_NAME if _localappdata else Path.home() / "AppData" / "Local" / APP_NAME
    XDG_CONFIG_HOME = APP_CONFIG_DIR.parent
    XDG_STATE_HOME = APP_STATE_DIR.parent
else:
    # Standard Linux / XDG paths
    XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    XDG_STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    APP_CONFIG_DIR = XDG_CONFIG_HOME / APP_NAME
    APP_STATE_DIR = XDG_STATE_HOME / APP_NAME

# Primary session file path (in config directory with restricted permissions)
XDG_SESSION_FILE = APP_CONFIG_DIR / "session.json"
LEGACY_SESSION_FILE = Path.home() / ".session_state.json"


def get_default_session_file() -> Path:
    """
    Returns the resolved session storage path.
    Prioritizes existing session file. Automatically migrates legacy ~/.session_state.json
    into XDG_SESSION_FILE with secure permissions if present.
    """
    try:
        APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform != "win32":
            os.chmod(APP_CONFIG_DIR, 0o700)
    except Exception:
        pass

    if XDG_SESSION_FILE.exists():
        return XDG_SESSION_FILE

    if LEGACY_SESSION_FILE.exists():
        try:
            content = LEGACY_SESSION_FILE.read_text(encoding="utf-8")
            if sys.platform != "win32":
                flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                fd = os.open(str(XDG_SESSION_FILE), flags, 0o600)
                with open(fd, "w", encoding="utf-8") as f:
                    f.write(content)
            else:
                XDG_SESSION_FILE.write_text(content, encoding="utf-8")
            try:
                LEGACY_SESSION_FILE.unlink()
            except Exception:
                pass
            return XDG_SESSION_FILE
        except Exception:
            return LEGACY_SESSION_FILE

    return XDG_SESSION_FILE


def get_default_desktop_path() -> Path:
    """
    Returns the resolved path to the user's active Desktop.
    On Windows, checks Windows Registry (User Shell Folders) to accurately handle
    OneDrive Desktop redirection (e.g. C:\\Users\\User\\OneDrive\\Desktop).
    Falls back gracefully to Path.home() / 'Desktop'.
    On Linux, checks XDG desktop configuration before falling back.
    """
    if sys.platform == "win32":
        # 1. Try Windows Registry for active Desktop folder
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                desktop_dir, _ = winreg.QueryValueEx(key, "Desktop")
                expanded = Path(os.path.expandvars(desktop_dir))
                if expanded.exists():
                    return expanded
        except Exception:
            pass

        # 2. Check OneDrive Desktop
        user_profile = Path(os.environ.get("USERPROFILE", Path.home()))
        for onedrive_candidate in (
            user_profile / "OneDrive" / "Desktop",
            user_profile / "OneDrive - Personal" / "Desktop",
        ):
            if onedrive_candidate.exists():
                return onedrive_candidate
    else:
        # Check XDG user directory if available
        xdg_desktop = os.environ.get("XDG_DESKTOP_DIR")
        if xdg_desktop and Path(xdg_desktop).exists():
            return Path(xdg_desktop)
        user_dirs_file = Path.home() / ".config" / "user-dirs.dirs"
        if user_dirs_file.exists():
            try:
                for line in user_dirs_file.read_text(encoding="utf-8").splitlines():
                    if line.startswith("XDG_DESKTOP_DIR="):
                        raw_dir = line.split("=", 1)[1].strip('"').strip("'")
                        resolved_dir = Path(os.path.expandvars(raw_dir.replace("$HOME", str(Path.home()))))
                        if resolved_dir.exists():
                            return resolved_dir
            except Exception:
                pass

    desktop = Path.home() / "Desktop"
    if desktop.exists():
        return desktop
    return Path.home()


# Default output spreadsheet path
DEFAULT_OUTPUT_PATH = get_default_desktop_path() / "fire_incidents_report.xlsx"

# -----------------------------------------------------------------------------
# Asset & Resource Resolution (Development & PyInstaller Frozen)
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE_DIR = Path(__file__).resolve().parent


def get_resource_path(relative_path: str | Path) -> Path:
    """
    Resolves resource paths cleanly across development mode,
    installed packages, and PyInstaller packaged executables (sys._MEIPASS).
    """
    rel = Path(relative_path)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / rel
    repo_asset = PROJECT_ROOT / rel
    if repo_asset.exists():
        return repo_asset
    pkg_asset = PACKAGE_DIR / rel
    if pkg_asset.exists():
        return pkg_asset
    return repo_asset


ASSETS_DIR = get_resource_path("assets")
LOGO_PATH = get_resource_path("assets/ldhvfd_logo.png")
CHECK_SVG_PATH = get_resource_path("assets/check.svg")
ICO_PATH = get_resource_path("assets/app_icon.ico")

# -----------------------------------------------------------------------------
# ESO Suite URLs & Date Defaults
# -----------------------------------------------------------------------------
ESO_SEARCH_URL = "https://www.esosuite.net/fireincidents/records/search"
ESO_INCIDENT_API_BASE = "https://www.esosuite.net/fireincidents/api/incident"


def get_default_start_date() -> str:
    """Returns the first day of the current month in YYYY-MM-DD format."""
    return date.today().replace(day=1).strftime("%Y-%m-%d")


def get_default_end_date() -> str:
    """Returns the current date in YYYY-MM-DD format."""
    return date.today().strftime("%Y-%m-%d")
