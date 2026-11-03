import pytest
from datetime import date, timedelta
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication
from eso_reports.gui import MainWindow, ScraperWorker, PopupCalendar


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["pytest-qt"])
    return app


def test_gui_window_initialization(qapp, tmp_path):
    out_file = tmp_path / "test_gui_output.xlsx"
    window = MainWindow(default_output=out_file)

    assert window.windowTitle() == "ESO Reports Generator"
    assert window.btn_start is not None
    assert window.btn_end is not None
    assert "Start Date:" in window.btn_start.text()
    assert "End Date:" in window.btn_end.text()
    assert window.btn_last_month is not None
    assert window.btn_this_month is not None
    assert window.btn_start_report is not None
    assert window.btn_start_report.isEnabled()
    assert window.btn_start_report.text() == "Start report"
    assert window.title_label is not None
    assert "ESO Report" in window.title_label.text()
    assert window.logo_label is not None

    # Header is inline horizontal layout with logo to the left of the title
    from PyQt6.QtWidgets import QHBoxLayout
    controls_widget = window.centralWidget().layout().itemAt(1).widget()
    header_layout = controls_widget.layout().itemAt(0)
    assert isinstance(header_layout, QHBoxLayout)
    assert header_layout.itemAt(0).widget() == window.logo_label
    assert header_layout.itemAt(1).widget() == window.title_label

    # Log is hidden in compact window (buttons centered vertically)
    assert window.log_window.isHidden()

    # Log is shown when window has enough room / expanded
    window.resize(580, 750)
    window._update_log_visibility()
    assert not window.log_window.isHidden()

    # Log hides again when window is resized compact
    window.resize(560, 480)
    window._update_log_visibility()
    assert window.log_window.isHidden()


def test_gui_presets(qapp, tmp_path):
    out_file = tmp_path / "test_gui_output.xlsx"
    window = MainWindow(default_output=out_file)

    # Test "This Month"
    window._set_preset_this_month()
    start = window.start_date.toPyDate()
    end = window.end_date.toPyDate()
    assert start.day == 1
    assert start.month == date.today().month
    assert end == date.today()
    assert f"Start Date: {window.start_date.toString('MM/dd/yyyy')}" == window.btn_start.text()

    # Test "Last Month"
    window._set_preset_last_month()
    start_lm = window.start_date.toPyDate()
    end_lm = window.end_date.toPyDate()
    today = date.today()
    first_of_this_month = today.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)
    assert start_lm == first_of_prev_month
    assert end_lm == last_of_prev_month


def test_popup_calendar(qapp):
    from PyQt6.QtCore import Qt
    cal = PopupCalendar()
    assert bool(cal.windowFlags() & Qt.WindowType.Popup)

    selected = None
    def on_date(d):
        nonlocal selected
        selected = d

    cal.callback = on_date
    test_d = QDate(2026, 9, 20)
    cal._handle_click(test_d)
    assert selected == test_d


def test_scraper_worker_init(tmp_path):
    out_file = tmp_path / "worker_output.xlsx"
    worker = ScraperWorker(
        start_date="2026-09-01",
        end_date="2026-09-30",
        output_path=out_file,
    )
    assert worker.start_date == "2026-09-01"
    assert worker.end_date == "2026-09-30"
    assert worker.output_path == out_file.resolve()


def test_gui_buttons_always_centered(qapp, tmp_path):
    out_file = tmp_path / "worker_output.xlsx"
    window = MainWindow(default_output=out_file)
    window.show()

    # 1. Compact mode (height 480): buttons centered, log hidden
    window.resize(560, 480)
    window._update_log_visibility()
    qapp.processEvents()
    controls_widget = window.centralWidget().layout().itemAt(1).widget()
    btn_center = controls_widget.y() + controls_widget.height() / 2
    win_center = window.height() / 2
    assert abs(btn_center - win_center) <= 2.0
    assert window.log_window.isHidden()

    # 2. Expanded / Full Screen mode (height 800): buttons STILL centered, log visible below
    window.resize(600, 800)
    window._update_log_visibility()
    qapp.processEvents()
    btn_center = controls_widget.y() + controls_widget.height() / 2
    win_center = window.height() / 2
    assert abs(btn_center - win_center) <= 2.0
    assert not window.log_window.isHidden()


def test_first_four_buttons_uniform_styling(qapp, tmp_path):
    out_file = tmp_path / "worker_output.xlsx"
    window = MainWindow(default_output=out_file)

    # First four buttons: Start Date, End Date, Last Month, This Month
    first_four = [window.btn_start, window.btn_end, window.btn_last_month, window.btn_this_month]

    for btn in first_four:
        # Check uniform fixed height
        assert btn.maximumHeight() == 40
        assert btn.minimumHeight() == 40
        # No presetBtn objectName differentiating them
        assert btn.objectName() != "presetBtn"


def test_completion_status_ux_no_prompt(qapp, tmp_path, monkeypatch):
    out_file = tmp_path / "completed_report.xlsx"
    window = MainWindow(default_output=out_file)

    assert window.status_label is not None
    assert window.status_icon is not None
    assert window.status_label.text() == ""
    assert window.status_icon.pixmap().isNull()

    # Prevent live background scraping during unit test
    monkeypatch.setattr(ScraperWorker, "start", lambda self: None)

    # Test "In progress..." state during generation
    window._start_generation()
    assert window.status_label.text() == "In progress..."
    assert window.status_icon.pixmap().isNull()
    assert not window.btn_start_report.isEnabled()
    assert window.btn_start_report.text() == "Running..."

    # Call _on_finished with success - should set status to "Done" (no period) with SVG check to its right
    window._on_finished(True, str(out_file), {}, "Success")
    assert window.status_label.text() == "Done"
    assert not window.status_icon.pixmap().isNull()
    assert window.btn_start_report.isEnabled()
    assert window.btn_start_report.text() == "Start report"

    # Reset on date change
    window._on_start_date_picked(QDate(2026, 9, 1))
    assert window.status_label.text() == ""
    assert window.status_icon.pixmap().isNull()

    # Set again and test reset on preset click
    window._on_finished(True, str(out_file), {}, "Success")
    assert window.status_label.text() == "Done"
    assert not window.status_icon.pixmap().isNull()
    window._set_preset_last_month()
    assert window.status_label.text() == ""
    assert window.status_icon.pixmap().isNull()

    # Assert no open report button exists on MainWindow
    assert not hasattr(window, "btn_open_report")

    # Test failure feedback: status label shows "Failed" in red without modal popup
    window._on_finished(False, "", {}, "Connection error occurred")
    assert window.status_label.text() == "Failed"
    assert window.status_icon.pixmap().isNull()
    assert "ef4444" in window.status_label.styleSheet()
    assert window.btn_start_report.isEnabled()
    assert window.btn_start_report.text() == "Start report"


def test_login_required_status_cleared_on_continue(qapp, tmp_path):
    """Verify that 'Login Required...' displays during MFA and clears once authenticated."""
    out_file = tmp_path / "login_flow_report.xlsx"
    window = MainWindow(default_output=out_file)

    # When log indicates re-authentication / MFA is required
    window._on_log("Opening browser for re-authentication...")
    assert window.status_label.text() == "Login Required..."
    assert "eab308" in window.status_label.styleSheet()

    # Once user logs in and authentication succeeds, status goes away while working
    window._on_log("Authentication success.")
    assert window.status_label.text() == ""

    # Also verify that subsequent continuation logs clear it if earlier logs were missed
    window._on_log("Waiting for user credentials and multi-factor authentication (MFA)...")
    assert window.status_label.text() == "Login Required..."
    window._on_log("• Connected to ESO Suite. Filtering search grid...")
    assert window.status_label.text() == ""


def test_popup_calendar_ms_forms_style(qapp):
    from PyQt6.QtWidgets import QToolButton
    cal = PopupCalendar()
    assert cal.isDateEditEnabled() is False
    assert cal.width() == 300
    assert cal.height() == 240

    prev_btn = cal.findChild(QToolButton, "qt_calendar_prevmonth")
    next_btn = cal.findChild(QToolButton, "qt_calendar_nextmonth")
    assert prev_btn is not None and prev_btn.text() == "‹"
    assert next_btn is not None and next_btn.text() == "›"


def test_scraper_worker_date_format_and_pixmap(qapp, tmp_path):
    from eso_reports.gui import load_check_pixmap
    from eso_reports.scraper import format_date_for_eso

    pixmap = load_check_pixmap(18)
    assert not pixmap.isNull()
    assert pixmap.width() == 18
    assert pixmap.height() == 18

    # Ensure format_date_for_eso outputs MM/DD/YYYY matching the buttons
    assert format_date_for_eso("2026-09-01") == "09/01/2026"
    assert format_date_for_eso("09/01/2026") == "09/01/2026"


def test_scraper_worker_logging_pipeline(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from contextlib import contextmanager

    out_file = tmp_path / "worker_output.xlsx"
    worker = ScraperWorker(
        start_date="2026-09-01",
        end_date="2026-09-30",
        output_path=out_file,
    )

    emitted_logs = []
    worker.log_signal.connect(lambda msg: emitted_logs.append(msg))
    finished_results = []
    worker.finished_signal.connect(lambda *args: finished_results.append(args))

    @contextmanager
    def mock_launch_auth(self, headless=True):
        self._log("Found saved session file: .session_state.json")
        self._log("Session is valid and active.")
        yield (MagicMock(), MagicMock())

    from eso_reports.auth import SessionManager
    from eso_reports.scraper import ESOScraper
    import eso_reports.gui as gui_module

    monkeypatch.setattr(SessionManager, "launch_authenticated_context", mock_launch_auth)

    def mock_search_and_extract(self, start_date, end_date):
        self._log("Connecting to ESO Records Search portal: https://www.esosuite.net/fireincidents/records/search...")
        self._log("Incident CO15202600444 found.")
        self._log("Scanning incidents complete.")
        return []

    monkeypatch.setattr(ESOScraper, "search_and_extract", mock_search_and_extract)

    # Run worker synchronously
    worker.run()

    # Check emissions
    assert any("Starting report for 09/01/2026 to 09/30/2026..." in m for m in emitted_logs)
    assert any("Verifying authentication..." in m for m in emitted_logs)
    assert any("Found saved session file:" in m for m in emitted_logs)
    assert any("Session is valid and active." in m for m in emitted_logs)
    assert any("Connecting to ESO Records Search portal:" in m for m in emitted_logs)
    assert any("Incident CO15202600444 found." in m for m in emitted_logs)
    assert any("Scanning incidents complete." in m for m in emitted_logs)
    assert any("Analyzing rosters and attendance..." in m for m in emitted_logs)
    assert any("Normalizing personnel names and building department roster..." in m for m in emitted_logs)
    assert any("Creating plain-text Excel workbook" in m for m in emitted_logs)
    assert any(f"Saving Excel workbook to {out_file.resolve()}" in m for m in emitted_logs)
    assert any("Workbook saved successfully." in m for m in emitted_logs)
    assert any("Done." in m for m in emitted_logs)
    assert len(finished_results) == 1
    assert finished_results[0][0] is True


def test_gui_manage_members_dialog(qapp, tmp_path, monkeypatch):
    from eso_reports.gui import MemberManagerDialog, MemberEditDialog
    from eso_reports.models import Member
    import eso_reports.gui as gui_module

    fake_members_file = tmp_path / "members.json"
    monkeypatch.setattr(gui_module, "load_members", lambda: [
        Member(name="Wellons, Charles", primary_id="1534", aliases=["CHF 15", "1534"], active=True),
        Member(name="Glass, Lucas", primary_id="1545", aliases=["1545"], active=False),
    ])

    saved_members_capture = []
    monkeypatch.setattr(gui_module, "save_members", lambda m: saved_members_capture.extend(m))

    dialog = MemberManagerDialog()
    assert dialog.table.rowCount() == 2
    assert dialog.table.item(0, 0).text() == "Wellons, Charles"
    assert dialog.table.item(0, 1).text() == "1534"
    assert "CHF 15" in dialog.table.item(0, 2).text()
    assert dialog.table.item(0, 3).text() == "Active"
    assert dialog.table.item(1, 3).text() == "Inactive"

    # Test MemberEditDialog validation
    edit_dlg = MemberEditDialog()
    edit_dlg.edit_name.setText("")
    # Empty name should not save
    monkeypatch.setattr(gui_module.QMessageBox, "warning", lambda *args: None)
    edit_dlg._on_save()
    assert edit_dlg.result_member is None

    edit_dlg.edit_name.setText("Garber, James | 1539")
    edit_dlg.edit_id.setText("1539")
    edit_dlg.edit_aliases.setText("CAPT 15, 15-39")
    edit_dlg.chk_active.setChecked(True)
    edit_dlg._on_save()

    assert edit_dlg.result_member is not None
    assert edit_dlg.result_member.name == "Garber, James"
    assert edit_dlg.result_member.primary_id == "1539"
    assert "1539" in edit_dlg.result_member.aliases
    assert "CAPT 15" in edit_dlg.result_member.aliases

    # Add member to manager dialog
    dialog.members.append(edit_dlg.result_member)
    dialog._populate_table()
    assert dialog.table.rowCount() == 3

    # Save and close
    dialog._save_and_close()
    assert len(saved_members_capture) == 3
    assert any(m.name == "Garber, James" for m in saved_members_capture)




