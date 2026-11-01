from unittest.mock import MagicMock, patch
from pathlib import Path
from src.auth import SessionManager


def test_session_manager_launch_authenticated_context(tmp_path: Path):
    session_file = tmp_path / ".session_state.json"
    session_mgr = SessionManager(session_path=session_file)

    mock_context = MagicMock()
    mock_browser = MagicMock()
    mock_context.browser = mock_browser

    with patch.object(session_mgr, "get_authenticated_context", return_value=mock_context) as mock_get:
        with session_mgr.launch_authenticated_context(headless=True) as (browser, context):
            assert browser == mock_browser
            assert context == mock_context
            mock_get.assert_called_once()

        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()


def test_interactive_login_closes_visible_browser_and_returns_headless(tmp_path: Path):
    session_file = tmp_path / ".session_state.json"
    logs = []
    session_mgr = SessionManager(session_path=session_file, log_callback=lambda m: logs.append(m))

    mock_playwright = MagicMock()
    headful_browser = MagicMock()
    headful_context = MagicMock()
    headful_page = MagicMock()
    headful_browser.new_context.return_value = headful_context
    headful_context.new_page.return_value = headful_page

    headless_browser = MagicMock()
    headless_context = MagicMock()
    headless_browser.new_context.return_value = headless_context

    # First launch is headful (interactive), second is headless
    mock_playwright.chromium.launch.side_effect = [headful_browser, headless_browser]

    ctx = session_mgr.interactive_login(mock_playwright, return_headless=True)

    # 1. Interactive browser must be closed
    headful_page.close.assert_called_once()
    headful_context.close.assert_called_once()
    headful_browser.close.assert_called_once()

    # 2. Storage state must be saved
    headful_context.storage_state.assert_called_once_with(path=str(session_file))

    # 3. Headless browser launched and context returned
    mock_playwright.chromium.launch.assert_called_with(headless=True)
    assert ctx == headless_context

    # 4. Check detailed logging tells
    assert any("Opening browser for re-authentication..." in log for log in logs)
    assert any("Authentication success." in log for log in logs)
    assert any("Closing interactive authentication browser..." in log for log in logs)
    assert any("Initializing headless background browser..." in log for log in logs)


def test_get_authenticated_context_expired_session_triggers_reauth(tmp_path: Path):
    session_file = tmp_path / ".session_state.json"
    session_file.write_text("{}")
    logs = []
    session_mgr = SessionManager(session_path=session_file, log_callback=lambda m: logs.append(m))

    mock_playwright = MagicMock()
    expired_browser = MagicMock()
    expired_context = MagicMock()
    mock_playwright.chromium.launch.return_value = expired_browser
    expired_browser.new_context.return_value = expired_context

    with patch.object(session_mgr, "is_session_valid", return_value=False):
        with patch.object(session_mgr, "interactive_login", return_value=MagicMock()) as mock_reauth:
            session_mgr.get_authenticated_context(mock_playwright, headless=True)

            mock_reauth.assert_called_once()
            assert any("Authentication failed." in log for log in logs)


def test_legacy_session_migration_to_xdg(tmp_path: Path, monkeypatch):
    import os
    import stat
    from src import config

    fake_config_home = tmp_path / ".config"
    fake_legacy_file = tmp_path / ".session_state.json"
    fake_legacy_file.write_text('{"cookies": [{"name": "auth", "value": "secret"}]}', encoding="utf-8")

    monkeypatch.setattr(config, "XDG_CONFIG_HOME", fake_config_home)
    monkeypatch.setattr(config, "APP_CONFIG_DIR", fake_config_home / "eso-reports")
    monkeypatch.setattr(config, "XDG_SESSION_FILE", fake_config_home / "eso-reports" / "session.json")
    monkeypatch.setattr(config, "LEGACY_SESSION_FILE", fake_legacy_file)

    resolved = config.get_default_session_file()
    assert resolved == fake_config_home / "eso-reports" / "session.json"
    assert resolved.exists()
    assert '{"cookies":' in resolved.read_text(encoding="utf-8")
    assert not fake_legacy_file.exists()
    mode = stat.S_IMODE(os.stat(resolved).st_mode)
    assert mode == 0o600


def test_corrupted_session_file_recovers_to_interactive_login(tmp_path: Path):
    session_file = tmp_path / "corrupted_session.json"
    session_file.write_text("NOT_VALID_JSON{:::}}")
    logs = []
    session_mgr = SessionManager(session_path=session_file, log_callback=lambda m: logs.append(m))

    mock_playwright = MagicMock()
    with patch.object(session_mgr, "interactive_login", return_value=MagicMock()) as mock_interactive:
        session_mgr.get_authenticated_context(mock_playwright, headless=True)
        mock_interactive.assert_called_once()
        assert not session_file.exists()
        assert any("corrupted" in log for log in logs)



