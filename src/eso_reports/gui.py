"""
Simple, Clean Desktop Graphical User Interface (GUI) for ESO Suite Reports.
Dark Mode with form-style popup calendar selectors and balanced layout.
"""

from __future__ import annotations
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QByteArray, QDate, QPoint, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QSizePolicy,
    QPushButton,
    QLabel,
    QTextEdit,
    QMessageBox,
    QCalendarWidget,
    QToolButton,
)

from .config import (
    get_default_session_file,
    DEFAULT_OUTPUT_PATH,
    LOGO_PATH,
    CHECK_SVG_PATH,
    ICO_PATH,
)
from .auth import SessionManager, find_system_browser
from .scraper import ESOScraper, format_date_for_eso
from .aggregator import build_report_dataset
from .excel_exporter import export_report_to_excel


def load_check_pixmap(size: int = 18) -> QPixmap:
    """Renders the two-lined vector checkmark SVG to a crisp transparent QPixmap."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    if CHECK_SVG_PATH.exists():
        renderer = QSvgRenderer(str(CHECK_SVG_PATH))
    else:
        svg_data = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" '
            'stroke="#22c55e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            '<polyline points="20 6 9 17 4 12"></polyline></svg>'
        )
        renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap

DARK_THEME_STYLE = """
QMainWindow {
    background-color: #0f172a;
}

QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #f1f5f9;
}

QLabel#headerTitle {
    color: #f8fafc;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: 0.5px;
    margin: 0px;
}

QPushButton {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
    color: #f8fafc;
    min-height: 22px;
}

QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}

QPushButton:pressed {
    background-color: #0f172a;
}

QPushButton#startReportBtn {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: 700;
    min-width: 180px;
    min-height: 24px;
}

QPushButton#startReportBtn:hover {
    background-color: #1d4ed8;
}

QPushButton#startReportBtn:disabled {
    background-color: #1e3a8a;
    color: #64748b;
}

QTextEdit {
    background-color: #020617;
    color: #cbd5e1;
    border: 1px solid #1e293b;
    border-radius: 6px;
    font-family: "DejaVu Sans Mono", "Courier New", Consolas, monospace;
    font-size: 12px;
    padding: 10px;
    line-height: 1.4;
}

/* Microsoft Forms / Fluent style Dark Mode Calendar Popup */
QCalendarWidget {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px;
}

QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: #0f172a;
    border-radius: 6px;
    min-height: 34px;
    margin-bottom: 6px;
}

QCalendarWidget QToolButton {
    background-color: transparent;
    color: #f8fafc;
    font-size: 13px;
    font-weight: 600;
    border: none;
    border-radius: 4px;
    padding: 3px 6px;
}

QCalendarWidget QToolButton:hover {
    background-color: #334155;
    color: #38bdf8;
}

QCalendarWidget QToolButton#qt_calendar_prevmonth,
QCalendarWidget QToolButton#qt_calendar_nextmonth {
    font-size: 16px;
    font-weight: bold;
    min-width: 24px;
    qproperty-icon: none;
}

QCalendarWidget QToolButton#qt_calendar_prevmonth:hover,
QCalendarWidget QToolButton#qt_calendar_nextmonth:hover {
    background-color: #334155;
}

QCalendarWidget QMenu {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
}

QCalendarWidget QSpinBox {
    background-color: #0f172a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 2px 4px;
}

QCalendarWidget QHeaderView::section {
    background-color: #1e293b;
    color: #94a3b8;
    font-weight: 600;
    font-size: 11px;
    border: none;
    padding: 3px 0px;
}

QCalendarWidget QTableView {
    background-color: #1e293b;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    border: none;
    outline: none;
}

QCalendarWidget QAbstractItemView:enabled {
    background-color: #1e293b;
    color: #f1f5f9;
    font-size: 12px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QCalendarWidget QAbstractItemView:disabled {
    color: #475569;
}
"""


class PopupCalendar(QCalendarWidget):
    """
    Standard Microsoft Forms / Fluent style calendar popup attached directly below the date button.
    Clean chevrons, standard 7-column day layout, dismisses on outside click or date selection.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.setGridVisible(False)
        self.setDateEditEnabled(False)
        self.setFixedSize(300, 240)

        prev_btn = self.findChild(QToolButton, "qt_calendar_prevmonth")
        next_btn = self.findChild(QToolButton, "qt_calendar_nextmonth")
        if prev_btn:
            prev_btn.setIcon(QIcon())
            prev_btn.setText("‹")
        if next_btn:
            next_btn.setIcon(QIcon())
            next_btn.setText("›")

        self.clicked.connect(self._handle_click)
        self.callback = None

    def _handle_click(self, qdate: QDate):
        if self.callback:
            self.callback(qdate)
        self.close()

    def popup_below(self, button: QPushButton, current_date: QDate, callback):
        self.callback = callback
        self.setSelectedDate(current_date)
        # Position anchored directly below the clicked button
        pos = button.mapToGlobal(QPoint(0, button.height() + 3))
        self.move(pos)
        self.show()


class ScraperWorker(QThread):
    """Background worker thread to execute ESO extraction without freezing the UI."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, dict, str)

    def __init__(self, start_date: str, end_date: str, output_path: Path):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date
        self.output_path = Path(output_path).expanduser().resolve()

    def run(self):
        try:
            start_disp = format_date_for_eso(self.start_date)
            end_disp = format_date_for_eso(self.end_date)
            self.log_signal.emit(f"Starting report for {start_disp} to {end_disp}...")
            self.log_signal.emit("Verifying authentication...")
            session_file = get_default_session_file()
            session_mgr = SessionManager(
                session_path=session_file,
                log_callback=lambda msg: self.log_signal.emit(msg),
            )

            with session_mgr.launch_authenticated_context(headless=True) as (browser, context):
                self.log_signal.emit("Authentication complete.")
                scraper = ESOScraper(
                    context=context,
                    log_callback=lambda msg: self.log_signal.emit(msg),
                )
                incidents = scraper.search_and_extract(self.start_date, self.end_date)

                self.log_signal.emit("Analyzing rosters and attendance...")
                dataset = build_report_dataset(
                    incidents=incidents,
                    start_date=start_disp,
                    end_date=end_disp,
                    log_callback=lambda msg: self.log_signal.emit(msg),
                )

                self.log_signal.emit(f"Writing to {self.output_path}...")
                out_file = export_report_to_excel(
                    dataset,
                    self.output_path,
                    log_callback=lambda msg: self.log_signal.emit(msg),
                )

                metrics = {
                    "total_active": dataset.total_incidents,
                    "total_inactive": len(dataset.inactive_incidents),
                    "roster_count": len(dataset.roster),
                    "apparatus_count": len(dataset.apparatus_summaries),
                }

                self.log_signal.emit("Done.")
                self.finished_signal.emit(True, str(out_file), metrics, "Success")
        except Exception as e:
            self.log_signal.emit(f"Error: {e}")
            self.finished_signal.emit(False, "", {}, str(e))


class MainWindow(QMainWindow):
    """
    Clean, simple desktop window in Dark Mode.
    Layout:
      - Controls (Logo, Title, Date Buttons, Presets, Start Report) are ALWAYS centered vertically.
      - Row 1: Start Date and End Date buttons side by side (with form popup calendar).
      - Row 2: Last Month and This Month buttons right below them.
      - Row 3: Centered Start Report button.
      - Row 4: Terminal-style log window spanning from below buttons to the bottom of the screen.
    """

    def __init__(self, default_output: Path = DEFAULT_OUTPUT_PATH):
        super().__init__()
        self.output_path = default_output
        self.worker: Optional[ScraperWorker] = None
        self.generated_report_path: Optional[str] = None

        self.setWindowTitle("ESO Report Generator")
        if ICO_PATH.exists():
            self.setWindowIcon(QIcon(str(ICO_PATH)))
        elif LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))
        self.resize(560, 480)
        self.setMinimumSize(480, 400)
        self.setStyleSheet(DARK_THEME_STYLE)

        # Dates state (default to Current Month)
        today = date.today()
        first_of_this_month = today.replace(day=1)

        self.start_date = QDate(first_of_this_month.year, first_of_this_month.month, 1)
        self.end_date = QDate(today.year, today.month, today.day)

        # SVG checkmark pixmap
        self.check_pixmap = load_check_pixmap(18)

        # Reusable popup calendar
        self.cal_popup = PopupCalendar(self)

        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 16, 20, 16)

        # Top spacer widget: equal stretch to keep buttons ALWAYS vertically centered
        self.top_space = QWidget()
        main_layout.addWidget(self.top_space, 1)

        # Controls container: fixed height, stretch 0
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(10)

        # Header: Lyn-Dan Heights Emblem (left) + Title (right) in inline horizontal layout
        header_layout = QHBoxLayout()
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.setSpacing(14)
        header_layout.setContentsMargins(0, 0, 0, 6)

        if LOGO_PATH.exists():
            self.logo_label = QLabel()
            pixmap = QPixmap(str(LOGO_PATH)).scaled(
                56, 56,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_label.setPixmap(pixmap)
            self.logo_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            header_layout.addWidget(self.logo_label)

        self.title_label = QLabel("ESO Report Generator")
        self.title_label.setObjectName("headerTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(self.title_label)

        controls_layout.addLayout(header_layout)

        # Row 1: Two buttons side by side that let you select the start and end dates
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        self.btn_start = QPushButton()
        self.btn_start.setFixedHeight(40)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self._select_start_date)
        row1.addWidget(self.btn_start)

        self.btn_end = QPushButton()
        self.btn_end.setFixedHeight(40)
        self.btn_end.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_end.clicked.connect(self._select_end_date)
        row1.addWidget(self.btn_end)

        controls_layout.addLayout(row1)

        # Row 2: Two buttons right below them that let you select last month or this month
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        self.btn_last_month = QPushButton("Last Month")
        self.btn_last_month.setFixedHeight(40)
        self.btn_last_month.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_last_month.clicked.connect(self._set_preset_last_month)
        row2.addWidget(self.btn_last_month)

        self.btn_this_month = QPushButton("This Month")
        self.btn_this_month.setFixedHeight(40)
        self.btn_this_month.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_this_month.clicked.connect(self._set_preset_this_month)
        row2.addWidget(self.btn_this_month)

        controls_layout.addLayout(row2)

        # Row 3: Centered Start report button with status indicator (In progress... / Done + SVG check)
        row3 = QHBoxLayout()
        row3.setSpacing(10)
        row3.addStretch(1)

        self.left_spacer = QWidget()
        self.left_spacer.setFixedWidth(130)
        row3.addWidget(self.left_spacer)

        self.btn_start_report = QPushButton("Start report")
        self.btn_start_report.setObjectName("startReportBtn")
        self.btn_start_report.setFixedHeight(44)
        self.btn_start_report.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start_report.clicked.connect(self._start_generation)
        row3.addWidget(self.btn_start_report)

        self.status_container = QWidget()
        self.status_container.setFixedWidth(130)
        status_layout = QHBoxLayout(self.status_container)
        status_layout.setContentsMargins(8, 0, 0, 0)
        status_layout.setSpacing(6)
        status_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 13px; font-weight: 700;")
        status_layout.addWidget(self.status_label)

        self.status_icon = QLabel()
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        status_layout.addWidget(self.status_icon)

        row3.addWidget(self.status_container)

        row3.addStretch(1)
        controls_layout.addLayout(row3)

        main_layout.addWidget(controls_widget, 0)

        # Bottom spacer widget: used when log is hidden, keeps buttons centered
        self.bottom_space = QWidget()
        main_layout.addWidget(self.bottom_space, 1)

        # Row 4: Terminal-style log window (shown from below buttons to bottom of screen when room permits)
        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        self.log_window.setVisible(False)
        main_layout.addWidget(self.log_window, 1)

        self._update_date_labels()
        self.log_window.append("Ready.")
        self._update_log_visibility()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_log_visibility()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            self._update_log_visibility()

    def _update_log_visibility(self):
        """
        Keeps buttons ALWAYS centered vertically on the window.
        When window has room (height >= 640px, maximized, or fullscreen),
        the log is shown in the space below the buttons down to the bottom of the screen.
        """
        has_room = self.height() >= 640 or self.isMaximized() or self.isFullScreen()
        if has_room:
            self.bottom_space.setVisible(False)
            self.log_window.setVisible(True)
        else:
            self.log_window.setVisible(False)
            self.bottom_space.setVisible(True)

    def _update_date_labels(self):
        self.btn_start.setText(f"Start Date: {self.start_date.toString('MM/dd/yyyy')}")
        self.btn_end.setText(f"End Date: {self.end_date.toString('MM/dd/yyyy')}")

    def _select_start_date(self):
        self.cal_popup.popup_below(
            button=self.btn_start,
            current_date=self.start_date,
            callback=self._on_start_date_picked,
        )

    def _on_start_date_picked(self, qdate: QDate):
        self.start_date = qdate
        self.status_label.setText("")
        self.status_icon.clear()
        self._update_date_labels()

    def _select_end_date(self):
        self.cal_popup.popup_below(
            button=self.btn_end,
            current_date=self.end_date,
            callback=self._on_end_date_picked,
        )

    def _on_end_date_picked(self, qdate: QDate):
        self.end_date = qdate
        self.status_label.setText("")
        self.status_icon.clear()
        self._update_date_labels()

    def _set_preset_last_month(self):
        today = date.today()
        first_of_this_month = today.replace(day=1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        first_of_prev_month = last_of_prev_month.replace(day=1)
        self.start_date = QDate(first_of_prev_month.year, first_of_prev_month.month, first_of_prev_month.day)
        self.end_date = QDate(last_of_prev_month.year, last_of_prev_month.month, last_of_prev_month.day)
        self.status_label.setText("")
        self.status_icon.clear()
        self._update_date_labels()

    def _set_preset_this_month(self):
        today = date.today()
        first_of_month = today.replace(day=1)
        self.start_date = QDate(first_of_month.year, first_of_month.month, first_of_month.day)
        self.end_date = QDate(today.year, today.month, today.day)
        self.status_label.setText("")
        self.status_icon.clear()
        self._update_date_labels()

    def _start_generation(self):
        if self.start_date > self.end_date:
            QMessageBox.warning(self, "Invalid Date Range", "Start Date must be before or equal to End Date.")
            return

        start_str = self.start_date.toString("MM/dd/yyyy")
        end_str = self.end_date.toString("MM/dd/yyyy")

        self.status_label.setText("In progress...")
        self.status_label.setStyleSheet("color: #f97316; font-size: 13px; font-weight: 700;")
        self.status_icon.clear()

        self.btn_start_report.setEnabled(False)
        self.btn_start_report.setText("Running...")
        self.log_window.clear()

        self.worker = ScraperWorker(
            start_date=start_str,
            end_date=end_str,
            output_path=self.output_path,
        )
        self.worker.log_signal.connect(self._on_log)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_log(self, text: str):
        self.log_window.append(text)
        self.log_window.ensureCursorVisible()
        lower = text.lower()
        if "re-authentication" in lower or "multi-factor" in lower or "mfa" in lower:
            self.status_label.setText("Login Required...")
            self.status_label.setStyleSheet("color: #eab308; font-size: 13px; font-weight: 700;")
        elif "login" in self.status_label.text().lower():
            if any(k in lower for k in (
                "authentication success",
                "session state saved",
                "closing interactive",
                "headless",
                "connected to eso",
                "filtering",
                "searching",
                "incident",
                "scanning",
                "analyzing",
                "writing",
                "saving",
            )):
                self.status_label.setText("")

    def _on_finished(self, success: bool, output_path: str, metrics: dict, message: str):
        self.btn_start_report.setEnabled(True)
        self.btn_start_report.setText("Start report")

        if success:
            self.generated_report_path = output_path
            self.status_label.setText("Done")
            self.status_label.setStyleSheet("color: #22c55e; font-size: 13px; font-weight: 700;")
            self.status_icon.setPixmap(self.check_pixmap)
        else:
            self.generated_report_path = None
            self.status_label.setText("Failed")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 13px; font-weight: 700;")
            self.status_icon.clear()

    def closeEvent(self, event):
        """Safely terminate any background scraper worker thread when window is closed."""
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(1000)
            if self.worker.isRunning():
                self.worker.terminate()
                self.worker.wait(1000)
        event.accept()


def launch_gui(output_path: Path = DEFAULT_OUTPUT_PATH):
    """Entrypoint to start the PyQt6 application."""
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = "ESOSuite.ReportsGenerator.1_0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    # Ensure crisp rendering across Windows high-DPI scaling displays
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ESO Report Generator")
    if ICO_PATH.exists():
        app.setWindowIcon(QIcon(str(ICO_PATH)))
    elif LOGO_PATH.exists():
        app.setWindowIcon(QIcon(str(LOGO_PATH)))

    window = MainWindow(default_output=output_path)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_gui()
