"""
Authentication and session management for ESO Suite.
Supports persistent browser profiles, system browser executables (Edge, Chrome, Chromium),
interactive login with MFA, and session state persistence.
"""

from __future__ import annotations
from contextlib import contextmanager
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Callable, Iterator, Optional, Tuple
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright
from rich.console import Console

from .config import get_default_session_file, ESO_SEARCH_URL

logger = logging.getLogger(__name__)
console = Console()

DEFAULT_SESSION_FILE = get_default_session_file()


def find_system_browser() -> Optional[str]:
    """
    Finds installed system Chromium, Microsoft Edge, or Google Chrome executable on Windows.
    Prioritizes pre-installed Microsoft Edge on Windows, standard Google Chrome,
    Brave, or Windows Registry App Paths.
    """
    candidates = [
        # Standard Edge locations (64-bit and 32-bit Program Files)
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        # Standard Chrome locations
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        # Brave Browser
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
    # Also check Windows Registry App Paths
    try:
        import winreg
        for exe_key in ("msedge.exe", "chrome.exe", "brave.exe"):
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_key}",
                ) as key:
                    path, _ = winreg.QueryValueEx(key, "")
                    if path and Path(path).is_file():
                        candidates.append(path)
            except Exception:
                pass
    except Exception:
        pass

    try:
        for bin_name in ("msedge", "chrome", "brave"):
            found = shutil.which(bin_name)
            if found:
                candidates.append(found)
    except Exception:
        pass

    for p in candidates:
        if Path(p).is_file():
            return p
    return None


def _launch_browser(playwright: Playwright, launch_args: dict) -> Browser:
    """
    Launches a Chromium browser instance using the specified arguments.
    Gracefully falls back across executable paths, system channels (Edge, Chrome),
    and bundled Playwright Chromium if the primary candidate fails.
    """
    try:
        return playwright.chromium.launch(**launch_args)
    except Exception as e:
        logger.debug("Primary browser launch attempt failed: %s", e)
        # 1. If an executable_path failed, retry without it using channels/bundled
        if "executable_path" in launch_args:
            fallback = dict(launch_args)
            fallback.pop("executable_path", None)
            fallback.setdefault("channel", "msedge")
            try:
                return _launch_browser(playwright, fallback)
            except Exception:
                pass

        # 2. If a channel failed, cascade msedge -> chrome -> bundled
        if "channel" in launch_args:
            fallback_args = dict(launch_args)
            current_channel = fallback_args.get("channel")
            if current_channel == "msedge":
                fallback_args["channel"] = "chrome"
                try:
                    return playwright.chromium.launch(**fallback_args)
                except Exception:
                    pass
            fallback_args.pop("channel", None)
            try:
                return playwright.chromium.launch(**fallback_args)
            except Exception:
                pass

        raise e
class SessionManager:
    """Manages browser sessions and persistent authentication for ESO Suite."""

    def __init__(
        self,
        session_path: Optional[Path] = None,
        profile_dir: Optional[Path] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.session_path = Path(session_path) if session_path else get_default_session_file()
        self.profile_dir = Path(profile_dir) if profile_dir else None
        self.log_callback = log_callback

    def _log(self, message: str):
        console.print(message)
        if self.log_callback:
            clean = re.sub(r"\[/?[a-zA-Z0-9_\s#=]+\]", "", message)
            self.log_callback(clean)

    def is_session_valid(self, context: BrowserContext) -> bool:
        """
        Validates if the saved session has active access to the ESO fire incidents portal.
        """
        self._log("Testing saved session validity...")
        page = context.new_page()
        try:
            self._log(f"Navigating to {ESO_SEARCH_URL}...")
            page.goto(ESO_SEARCH_URL, wait_until="networkidle", timeout=20000)

            current_url = page.url.lower()
            if any(term in current_url for term in ("login", "signin", "idp", "identity", "auth")):
                self._log("Session redirected to login page. Saved session is expired.")
                return False

            login_inputs = page.locator("input[type='password'], input[name='Username'], input[name='password']").count()
            if login_inputs > 0:
                self._log("Password login prompt detected. Saved session is invalid.")
                return False

            self._log("Session is valid and active.")
            return True
        except Exception as e:
            self._log(f"Session validation check failed: {e}")
            return False
        finally:
            try:
                page.close()
            except Exception:
                pass

    def interactive_login(
        self,
        playwright: Playwright,
        browser_exe: Optional[str] = None,
        return_headless: bool = True,
    ) -> BrowserContext:
        """
        Launches an interactive browser session for manual login,
        supporting Agency ID, Username, Password, and MFA/DUO authentication.
        Once login succeeds, saves session state, closes the visible browser,
        and returns a background headless BrowserContext.
        """
        console.print("\n[bold yellow]═══ Interactive ESO Suite Login Required ═══[/bold yellow]")
        console.print("A browser window will open. Please:")
        console.print("1. Enter your Agency ID, Username, and Password.")
        console.print("2. Complete any Multi-Factor Authentication (MFA / Duo / SMS).")
        console.print("3. Wait until you reach the ESO Records Search or Dashboard page.")
        console.print("[yellow]The tool will automatically detect your login and save your session.[/yellow]\n")

        self._log("Opening browser for re-authentication...")
        launch_args = {
            "headless": False,
        }
        if browser_exe:
            launch_args["executable_path"] = browser_exe
        else:
            launch_args["channel"] = "msedge"

        browser = _launch_browser(playwright, launch_args)
        context = browser.new_context()
        page = context.new_page()

        page.goto(ESO_SEARCH_URL, timeout=60000)

        self._log("Waiting for user credentials and multi-factor authentication (MFA)...")
        try:
            page.wait_for_url(
                lambda url: "esosuite.net/fireincidents" in url and not any(k in url.lower() for k in ("login", "signin", "idp")),
                timeout=300000,
            )
            page.wait_for_load_state("networkidle", timeout=15000)
            self._log("Authentication success.")
        except Exception as e:
            self._log(f"Authentication wait failed: {e}")
            try:
                page.close()
                context.close()
                browser.close()
            except Exception:
                pass
            raise RuntimeError(f"Interactive authentication failed or timed out: {e}")

        # Persist storage state securely in %APPDATA%\eso-reports
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(self.session_path))
        self._log(f"Session state saved to {self.session_path.resolve()}.")

        # Close interactive browser window immediately so user cannot see or interfere with scraping
        self._log("Closing interactive authentication browser...")
        try:
            page.close()
            context.close()
            browser.close()
        except Exception:
            pass

        if return_headless:
            self._log("Initializing headless background browser...")
            headless_args = {"headless": True}
            if browser_exe:
                headless_args["executable_path"] = browser_exe
            else:
                headless_args["channel"] = "msedge"
            headless_browser = _launch_browser(playwright, headless_args)
            return headless_browser.new_context(storage_state=str(self.session_path))
        else:
            browser = _launch_browser(playwright, launch_args)
            return browser.new_context(storage_state=str(self.session_path))

    def get_authenticated_context(
        self,
        playwright: Playwright,
        headless: bool = True,
        force_login: bool = False,
    ) -> BrowserContext:
        """
        Returns an authenticated BrowserContext.
        Uses system browser if available, and existing session state file if valid.
        """
        system_browser = find_system_browser()
        if system_browser:
            self._log(f"Using system browser: {Path(system_browser).name}")

        launch_args = {"headless": headless}
        if system_browser:
            launch_args["executable_path"] = system_browser
        else:
            launch_args["channel"] = "msedge"

        session_valid_json = False
        if self.session_path.exists() and not force_login:
            try:
                import json
                raw_json = self.session_path.read_text(encoding="utf-8")
                session_data = json.loads(raw_json)
                if isinstance(session_data, dict):
                    session_valid_json = True
                else:
                    self._log("Saved session file format is invalid. Removing.")
                    try:
                        self.session_path.unlink()
                    except Exception:
                        pass
            except Exception as ex:
                self._log(f"Saved session file is corrupted ({ex}). Removing.")
                try:
                    self.session_path.unlink()
                except Exception:
                    pass

        if session_valid_json:
            self._log(f"Found saved session file: {self.session_path.resolve()}")
            browser = None
            context = None
            is_valid = False
            try:
                browser = _launch_browser(playwright, launch_args)
                context = browser.new_context(storage_state=str(self.session_path))

                if self.is_session_valid(context):
                    is_valid = True
                    return context
                else:
                    self._log("Authentication failed.")
            except Exception as e:
                self._log(f"Could not load saved session: {e}.")
            finally:
                if not is_valid:
                    if context is not None:
                        try:
                            context.close()
                        except Exception:
                            pass
                    if browser is not None:
                        try:
                            browser.close()
                        except Exception:
                            pass
        else:
            self._log("No saved session credentials found.")

        return self.interactive_login(playwright, browser_exe=system_browser, return_headless=headless)

    @contextmanager
    def launch_authenticated_context(
        self,
        headless: bool = True,
        force_login: bool = False,
    ) -> Iterator[Tuple[Optional[Browser], BrowserContext]]:
        """
        Context manager that handles Playwright lifecycle and returns an authenticated (browser, context) pair.
        Automatically closes context, browser, and playwright upon exit.
        """
        with sync_playwright() as playwright:
            context = self.get_authenticated_context(playwright, headless=headless, force_login=force_login)
            browser = context.browser
            try:
                yield browser, context
            finally:
                try:
                    context.close()
                except Exception:
                    pass
                if browser:
                    try:
                        browser.close()
                    except Exception:
                        pass
