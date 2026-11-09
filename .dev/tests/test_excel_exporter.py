"""
Tests for Excel export generation, plain text styling, Call Percentage, and Other tables.
"""

from pathlib import Path
import openpyxl
import pytest

from eso_reports.models import Incident, Member
from eso_reports.aggregator import build_report_dataset
from eso_reports.excel_exporter import export_report_to_excel, _format_cell_date, format_call_header


def test_format_cell_date():
    assert _format_cell_date("10/17/2026 20:25:06") == "10/17/2026 20:25"
    assert _format_cell_date("10/17/2026") == "10/17/2026"
    assert _format_cell_date("2026-10-17T20:25:06-04:00") == "10/17/2026 20:25"
    assert _format_cell_date("2026-10-17 20:25:06") == "10/17/2026 20:25"
    assert _format_cell_date("2026-10-17") == "10/17/2026"
    assert _format_cell_date("") == ""


def test_format_call_header():
    assert format_call_header("CO15202600356") == "#356"
    assert format_call_header("24-00101") == "#101"
    assert format_call_header("12") == "#012"


def test_excel_export_structure(tmp_path: Path):
    incidents = [
        Incident(
            incident_number="24-00101",
            incident_type="111 - Building fire",
            incident_date="10/17/2026 20:25",
            responders=["Wellons, Charles | 1534", "Glass, Lucas | 1545"],
            apparatus=["Engine 15", "POV"],
        ),
        Incident(
            incident_number="24-00102",
            incident_type="321 - EMS call",
            incident_date="10/17/2026 02:29",
            responders=["Wellons, Charles | 1534"],
            apparatus=["Engine 15"],
        ),
        Incident(
            incident_number="24-00103",
            incident_type="321 - EMS call",
            incident_date="10/15/2026 17:19",
            responders=["Glass, Lucas | 1545"],
            apparatus=["Station Standby"],
        ),
    ]

    dataset = build_report_dataset(incidents)
    output_file = tmp_path / "test_report.xlsx"

    result_path = export_report_to_excel(dataset, output_file)
    assert result_path.exists()

    wb = openpyxl.load_workbook(result_path)

    # 1. Verify sheet names: exactly 2 sheets ("Call Percentage" and "Other")
    assert wb.sheetnames == ["Call Percentage", "Other"]

    # 2. Verify Sheet 1: Call Percentage
    ws1 = wb["Call Percentage"]
    # Check headers: Unit #, Name, followed by #[last 3 digits] for each call
    expected_headers = ["Unit #", "Name", "#101", "#102", "#103", "Percentage"]
    actual_headers = [cell.value for cell in ws1[1]]
    assert actual_headers == expected_headers

    # Check freeze panes on C2 (freezes Unit # and Name columns, and top row)
    assert ws1.freeze_panes == "C2"

    # Check print title columns for multi-page printing
    assert "$A:$B" in str(ws1.print_title_cols)

    # Check font is Arial
    assert ws1.cell(row=1, column=1).font.name == "Arial"
    assert ws1.cell(row=2, column=1).font.name == "Arial"

    # Check all boxes outlined (cell border is set)
    assert ws1.cell(row=1, column=1).border.left.style == "thin"
    assert ws1.cell(row=2, column=1).border.left.style == "thin"

    # Unit # column should be bolded
    assert ws1.cell(row=2, column=1).font.bold is True

    # Check that unit numbers 1510 - 1564 are present
    unit_col_vals = [str(ws1.cell(row=r, column=1).value) for r in range(2, ws1.max_row + 1)]
    for u in range(1510, 1565):
        assert str(u) in unit_col_vals

    # Check 1534 row has Charles Wellons and correct Xs
    row_1534 = next(r for r in range(2, ws1.max_row + 1) if ws1.cell(row=r, column=1).value == "1534")
    assert ws1.cell(row=row_1534, column=2).value == "Charles Wellons"
    assert ws1.cell(row=row_1534, column=3).value == "X"  # Call 101
    assert ws1.cell(row=row_1534, column=4).value == "X"  # Call 102
    assert ws1.cell(row=row_1534, column=5).value in (None, "")  # Call 103

    # Check an unmapped unit number (e.g. 1522) has blank name
    row_1522 = next(r for r in range(2, ws1.max_row + 1) if ws1.cell(row=r, column=1).value == "1522")
    assert ws1.cell(row=row_1522, column=2).value in (None, "")

    # 3. Verify Sheet 2: Other
    ws2 = wb["Other"]

    # Freezing should be removed
    assert ws2.freeze_panes is None

    # Table 1: Incident Types in Cols A-B starting Row 1 (No "INCIDENT TYPES BREAKDOWN" header)
    assert ws2.cell(row=1, column=1).value == "Incident Type"
    assert ws2.cell(row=1, column=2).value == "Total Calls Made (%)"
    assert ws2.cell(row=1, column=1).font.name == "Arial"

    # Table 2: Apparatus in Cols D-E starting Row 1 (No "APPARATUS / RESOURCE BREAKDOWN" header)
    assert ws2.cell(row=1, column=4).value == "Apparatus"
    assert ws2.cell(row=1, column=5).value == "Total Calls Made (%)"
    assert ws2.cell(row=1, column=4).font.name == "Arial"

    # Table 3: Other in Cols H-I starting Row 1 (No "OTHER / INACTIVE REPORTS" header)
    assert ws2.cell(row=1, column=8).value == "Other"
    assert ws2.cell(row=1, column=9).value == "Description"
    assert ws2.cell(row=1, column=8).font.name == "Arial"

    # Check outer border on top tables
    assert ws2.cell(row=1, column=1).border.top.style == "medium"
    assert ws2.cell(row=1, column=4).border.top.style == "medium"
    assert ws2.cell(row=1, column=8).border.top.style == "medium"

    # Check debugging tables exist below top tables
    content_cells = [str(cell.value) for row in ws2.iter_rows(values_only=False) for cell in row if cell.value]
    assert "INCIDENT CAD & RADIO BREAKDOWN" in content_cells
    assert "UNMAPPED CALL SIGNS AUDIT LOG" in content_cells
    assert "UNMAPPED CALL SIGNS FREQUENCY SUMMARY" in content_cells


def test_excel_export_formatting_rules(tmp_path: Path):
    incidents = [
        Incident(incident_number="24-00101", incident_type="111 - Building fire",
                 responders=["Wellons, Charles | 1534"], apparatus=["Engine 15"]),
        Incident(incident_number="24-00102", incident_type="321 - EMS call",
                 responders=["Wellons, Charles | 1534"], apparatus=["Engine 15"]),
        Incident(incident_number="24-00103", incident_type="321 - EMS call",
                 responders=["Glass, Lucas | 1545"], apparatus=["Engine 15"]),
    ]
    out_file = tmp_path / "formatting.xlsx"
    export_report_to_excel(build_report_dataset(incidents), out_file)
    wb = openpyxl.load_workbook(out_file)
    ws1, ws2 = wb["Call Percentage"], wb["Other"]

    # Bold only on the Unit # column, including its header
    for ws in (ws1, ws2):
        for row in ws.iter_rows():
            for cell in row:
                expected = ws is ws1 and cell.column == 1
                if cell.value is not None:
                    assert bool(cell.font.bold) is expected, f"{ws.title}!{cell.coordinate}"

    # Percentage is the last column, formatted "x/n (y%)"
    pct_col = ws1.max_column
    assert ws1.cell(row=1, column=pct_col).value == "Percentage"
    rows = {ws1.cell(row=r, column=1).value: r for r in range(2, ws1.max_row + 1)}
    assert ws1.cell(row=rows["1534"], column=pct_col).value == "2/3 (66.7%)"
    assert ws1.cell(row=rows["1545"], column=pct_col).value == "1/3 (33.3%)"
    assert ws1.cell(row=rows["1510"], column=pct_col).value == "0/3 (0.0%)"

    # Every column with content is at least as wide as its longest text
    for ws in (ws1, ws2):
        for col in ws.columns:
            longest = max((len(str(c.value)) for c in col if c.value is not None), default=0)
            if longest:
                assert ws.column_dimensions[col[0].column_letter].width >= longest


def test_debug_tables_and_legend_sit_right_of_top_tables(tmp_path: Path):
    members = [
        Member(name="Garber, James Steven, Jr.", primary_id="1539",
               aliases=["1539", "CHF 15", "CF15", "CHIEF 15", "1501"], active=True),
    ]
    incidents = [
        Incident(
            incident_number="CO15202600356",
            incident_type="MVC",
            cad_notes="11/6/2026 17:19:49 - CHF 15 ENRT; 11/6/2026 17:20:11 - CHIEF 15 ST; "
                      "11/6/2026 17:21:00 - 1503 ENRT; 11/6/2026 17:22:00 - PMPR15",
        ),
    ]
    out_file = tmp_path / "legend.xlsx"
    export_report_to_excel(build_report_dataset(incidents, members_db=members), out_file)
    ws2 = openpyxl.load_workbook(out_file)["Other"]

    assert ws2.cell(row=1, column=11).value == "INCIDENT CAD & RADIO BREAKDOWN"
    assert ws2.cell(row=1, column=18).value == "CAD ENTRY LEGEND"
    assert all(ws2.cell(row=r, column=1).value != "INCIDENT CAD & RADIO BREAKDOWN" for r in range(1, ws2.max_row + 1))

    legend = {}
    r = 3
    while ws2.cell(row=r, column=18).value:
        legend[ws2.cell(row=r, column=18).value] = [ws2.cell(row=r, column=c).value for c in range(19, 23)]
        r += 1
    assert legend["CHF 15"] == ["1539", "James Steven Garber, Jr.", "Marks attendance", 1]
    assert legend["CHIEF 15"][:1] == ["1539"]
    assert legend["1503"][0] == "1503" and legend["1503"][2] == "Unit not on sheet"
    assert legend["PMPR15"][2] == "No match"

    # Audit log quotes only the CAD entry containing the mark, never the whole note
    snippets = [ws2.cell(row=x, column=14).value for x in range(1, ws2.max_row + 1)]
    assert "11/6/2026 17:21:00 - 1503 ENRT" in snippets


def test_excel_export_empty_dataset(tmp_path: Path):
    dataset = build_report_dataset([])
    output_file = tmp_path / "empty_report.xlsx"

    result_path = export_report_to_excel(dataset, output_file)
    assert result_path.exists()

    wb = openpyxl.load_workbook(result_path)
    assert wb.sheetnames == ["Call Percentage", "Other"]
    ws1 = wb["Call Percentage"]
    # Headers Unit #, Name
    assert ws1.cell(row=1, column=1).value == "Unit #"
    assert ws1.cell(row=1, column=2).value == "Name"
    # Unit 1510 still present
    assert ws1.cell(row=2, column=1).value == "1510"


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
    ws2 = wb["Other"]

    # Inactive report is listed in Table 3 (Cols H & I)
    found_inactive = False
    for r in range(2, ws2.max_row + 1):
        val = str(ws2.cell(row=r, column=8).value or "")
        if "260905-134412-LDHVFD" in val:
            found_inactive = True
            desc_val = str(ws2.cell(row=r, column=9).value or "")
            assert "09/05/2026" in desc_val
            break
    assert found_inactive


def test_excel_export_cad_marks_and_questionable_tokens(tmp_path: Path):
    members = [
        Member(name="Garber, James Steven, Jr.", primary_id="1539", aliases=["CHF 15", "1539"], active=True),
    ]

    incidents = [
        Incident(
            incident_number="CO15202600356",
            incident_type="MVC / VEHICLE ACCIDENT",
            incident_date="10/11/2026 18:25",
            responders=[],
            cad_notes="[18:25:00] CHG15 EN ROUTE POV\n[18:26:00] 1516 ON SCENE",
        ),
    ]

    dataset = build_report_dataset(incidents, members_db=members)
    out_file = tmp_path / "test_cad_questionable.xlsx"
    export_report_to_excel(dataset, out_file)

    wb = openpyxl.load_workbook(out_file)

    # Sheet 1: Unit 1516 tracked from CAD notes without mapped name has 'X'
    ws1 = wb["Call Percentage"]
    row_1516 = next(r for r in range(2, ws1.max_row + 1) if ws1.cell(row=r, column=1).value == "1516")
    assert ws1.cell(row=row_1516, column=2).value in (None, "")
    assert ws1.cell(row=row_1516, column=3).value == "X"

    # Sheet 2: Questionable mark CHG15 listed in Table 3 (Other column)
    ws2 = wb["Other"]
    found_chg15 = False
    for r in range(2, ws2.max_row + 1):
        if str(ws2.cell(row=r, column=8).value) in ("CHG15", "CHG 15"):
            found_chg15 = True
            desc = str(ws2.cell(row=r, column=9).value)
            # Description must say "from [call number] [date] [time] [incident type]"
            assert "from CO15202600356" in desc
            assert "10/11/2026 18:25" in desc
            assert "MVC / VEHICLE ACCIDENT" in desc
            break
    assert found_chg15


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
