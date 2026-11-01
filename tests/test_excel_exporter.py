"""
Tests for Excel export generation, plain text styling, Date column, and 2-column tables.
"""

from pathlib import Path
import openpyxl
import pytest

from src.models import Incident
from src.aggregator import build_report_dataset
from src.excel_exporter import export_report_to_excel, _format_cell_date


def test_format_cell_date():
    assert _format_cell_date("10/17/2026 20:25:06") == "10/17/2026 20:25"
    assert _format_cell_date("10/17/2026") == "10/17/2026"
    assert _format_cell_date("2026-10-17T20:25:06-04:00") == "10/17/2026 20:25"
    assert _format_cell_date("2026-10-17 20:25:06") == "10/17/2026 20:25"
    assert _format_cell_date("2026-10-17") == "10/17/2026"
    assert _format_cell_date("") == ""


def test_excel_export_structure(tmp_path: Path):
    incidents = [
        Incident(
            incident_number="24-00101",
            incident_type="111 - Building fire",
            incident_date="10/17/2026 20:25",
            responders=["Adams, J.", "Baker, M."],
            apparatus=["Engine 15", "POV"],
        ),
        Incident(
            incident_number="24-00102",
            incident_type="321 - EMS call",
            incident_date="10/17/2026 02:29",
            responders=["Adams, J.", "Clark, R."],
            apparatus=["Engine 15"],
        ),
        Incident(
            incident_number="24-00103",
            incident_type="321 - EMS call",
            incident_date="10/15/2026 17:19",
            responders=["Baker, M."],
            apparatus=["Station Standby"],
        ),
    ]

    dataset = build_report_dataset(incidents)
    output_file = tmp_path / "test_report.xlsx"

    result_path = export_report_to_excel(dataset, output_file)
    assert result_path.exists()

    wb = openpyxl.load_workbook(result_path)

    # Verify sheet names
    assert wb.sheetnames == ["Attendance Matrix", "Incident Types & Apparatus"]

    # 1. Verify Sheet 1: Attendance Matrix
    ws1 = wb["Attendance Matrix"]
    # Check headers with Date column
    expected_headers = ["Incident Number", "Incident Type", "Date", "Adams, J.", "Baker, M.", "Clark, R."]
    actual_headers = [cell.value for cell in ws1[1]]
    assert actual_headers == expected_headers

    # Check freeze panes on D2 (freezes Number, Type, Date and Header row)
    assert ws1.freeze_panes == "D2"

    # Verify plain text (no colored fill)
    for row in ws1.iter_rows(min_row=1, max_row=5, min_col=1, max_col=6):
        for cell in row:
            assert cell.fill.fill_type is None or cell.fill.start_color.rgb == "00000000"

    # Check incident row 1 (Row 2): 24-00101 -> Date, Adams X, Baker X, Clark blank
    assert ws1.cell(row=2, column=1).value == "24-00101"
    assert ws1.cell(row=2, column=2).value == "111 - Building fire"
    assert "10/17/2026" in str(ws1.cell(row=2, column=3).value)
    assert ws1.cell(row=2, column=4).value == "X"
    assert ws1.cell(row=2, column=5).value == "X"
    assert ws1.cell(row=2, column=6).value is None or ws1.cell(row=2, column=6).value == ""

    # Check summary row (Row 5: 3 incidents + header = row 5)
    assert ws1.cell(row=5, column=1).value == "Total Calls Made"
    assert ws1.cell(row=5, column=2).value == "Total Incidents: 3"
    assert ws1.cell(row=5, column=3).value in (None, "")
    assert ws1.cell(row=5, column=4).value == "2/3 (66.7%)"
    assert ws1.cell(row=5, column=5).value == "2/3 (66.7%)"
    assert ws1.cell(row=5, column=6).value == "1/3 (33.3%)"

    # 2. Verify Sheet 2: Incident Types & Apparatus (2 Columns)
    ws2 = wb["Incident Types & Apparatus"]
    
    # Header block
    assert ws2.cell(row=1, column=1).value == "INCIDENT TYPES BREAKDOWN"
    expected_headers_ws2 = ["Incident Type", "Total Calls Made (%)"]
    actual_headers_ws2 = [ws2.cell(row=2, column=1).value, ws2.cell(row=2, column=2).value]
    assert actual_headers_ws2 == expected_headers_ws2

    # Check freeze panes
    assert ws2.freeze_panes == "A3"

    # Check Incident types rows (2 columns)
    assert ws2.cell(row=3, column=1).value == "321 - EMS call"
    assert ws2.cell(row=3, column=2).value == "2/3 (66.7%)"

    assert ws2.cell(row=4, column=1).value == "111 - Building fire"
    assert ws2.cell(row=4, column=2).value == "1/3 (33.3%)"

    # Total row
    assert ws2.cell(row=5, column=1).value == "Total Incidents"
    assert ws2.cell(row=5, column=2).value == "3/3 (100.0%)"

    # Check Apparatus Section exists (2 columns)
    found_apparatus_section = False
    for r in range(6, ws2.max_row + 1):
        if ws2.cell(row=r, column=1).value == "APPARATUS / RESOURCE BREAKDOWN":
            found_apparatus_section = True
            header_row = r + 1
            assert ws2.cell(row=header_row, column=1).value == "Apparatus / Resource"
            assert ws2.cell(row=header_row, column=2).value == "Total Calls Made (%)"
            break
    assert found_apparatus_section


def test_excel_export_empty_dataset(tmp_path: Path):
    dataset = build_report_dataset([])
    output_file = tmp_path / "empty_report.xlsx"

    result_path = export_report_to_excel(dataset, output_file)
    assert result_path.exists()

    wb = openpyxl.load_workbook(result_path)
    assert wb.sheetnames == ["Attendance Matrix", "Incident Types & Apparatus"]
    ws1 = wb["Attendance Matrix"]
    assert ws1.cell(row=2, column=1).value == "Total Calls Made"
    assert ws1.cell(row=2, column=2).value == "Total Incidents: 0"


def test_excel_export_with_inactive_section(tmp_path: Path):
    incidents = [
        Incident(
            incident_number="CO15202600407",
            incident_type="Gas leak / gas odor",
            responders=["Adams, John"],
            status="ACTIVE",
        ),
        Incident(
            incident_number="260905-134412-LDHVFD",
            incident_type="Unknown Incident Type",
            incident_date="09/05/2026 13:44",
            responders=[],
            status="INACTIVE",
        ),
    ]

    dataset = build_report_dataset(incidents)
    out_file = tmp_path / "inactive_test.xlsx"
    export_report_to_excel(dataset, out_file)

    wb = openpyxl.load_workbook(out_file)
    ws1 = wb["Attendance Matrix"]
    # Only active incident on Sheet 1
    assert ws1.cell(row=2, column=1).value == "CO15202600407"
    assert ws1.cell(row=3, column=1).value == "Total Calls Made"

    ws2 = wb["Incident Types & Apparatus"]
    # Inactive section exists on Sheet 2
    found_inactive_section = False
    for r in range(1, ws2.max_row + 1):
        if ws2.cell(row=r, column=1).value == "OTHER / INACTIVE REPORTS":
            found_inactive_section = True
            header_row = r + 1
            assert ws2.cell(row=header_row, column=1).value == "Incident Number (Status)"
            data_row = r + 2
            assert "260905-134412-LDHVFD" in str(ws2.cell(row=data_row, column=1).value)
            break
    assert found_inactive_section


def test_excel_export_permission_error_fallback(tmp_path: Path, monkeypatch):
    incidents = [
        Incident(
            incident_number="CO15202600407",
            incident_type="Gas leak / gas odor",
            responders=["Adams, John"],
            status="ACTIVE",
        ),
    ]
    dataset = build_report_dataset(incidents)
    out_file = tmp_path / "locked_report.xlsx"

    # Simulate PermissionError on first save attempt, succeed on fallback attempt
    orig_save = openpyxl.Workbook.save
    first_attempt = True

    def mock_save(self, filename):
        nonlocal first_attempt
        if first_attempt:
            first_attempt = False
            raise PermissionError("Simulated locked file")
        return orig_save(self, filename)

    monkeypatch.setattr(openpyxl.Workbook, "save", mock_save)

    saved_path = export_report_to_excel(dataset, out_file)
    assert saved_path != out_file
    assert saved_path.exists()
    assert "locked_report_" in saved_path.name


