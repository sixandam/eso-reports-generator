"""
Excel report generation module using openpyxl.
Produces standardized ESO Report.xlsx with three worksheets:
- Sheet 1: Master Attendance Matrix (multi-source indicators: X, R, XR; Date column; freeze panes on D2)
- Sheet 2: Incident Types & Apparatus (2-column tables: Name and 'n/n (n%)')
- Sheet 3: CAD Notes & Radio Audit (Incident breakdown, unmapped call signs audit, frequency summary)
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Union
import openpyxl
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

from .models import ReportDataset

# Clean Plain Text Styles (no background fills or colored shading)
REGULAR_FONT = Font(name="Calibri", size=11)
BOLD_FONT = Font(name="Calibri", size=11, bold=True)

THIN_BORDER_SIDE = Side(style="thin", color="D3D3D3")
THIN_BORDER = Border(
    left=THIN_BORDER_SIDE,
    right=THIN_BORDER_SIDE,
    top=THIN_BORDER_SIDE,
    bottom=THIN_BORDER_SIDE,
)

SUMMARY_BORDER = Border(
    left=THIN_BORDER_SIDE,
    right=THIN_BORDER_SIDE,
    top=Side(style="thin", color="000000"),
    bottom=Side(style="double", color="000000"),
)

ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")


def _format_cell_date(date_str: str) -> str:
    """Formats incident timestamps into clean MM/DD/YYYY HH:MM or MM/DD/YYYY format."""
    if not date_str:
        return ""
    clean = str(date_str).strip()
    # Case 1: Slash format e.g. "10/17/2026 20:25:06" or "10/17/2026"
    if "/" in clean:
        parts = clean.split()
        if len(parts) >= 2:
            time_part = ":".join(parts[1].split(":")[:2])
            return f"{parts[0]} {time_part}"
        return parts[0]

    # Case 2: ISO format e.g. "2026-10-17T20:25:06-04:00", "2026-10-17 20:25:06", "2026-10-17"
    try:
        iso_clean = clean.replace(" ", "T").replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_clean)
        if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and "T" not in clean and ":" not in clean:
            return dt.strftime("%m/%d/%Y")
        return dt.strftime("%m/%d/%Y %H:%M")
    except Exception:
        pass
    return clean


def _auto_fit_columns(ws, min_width: int = 12, max_width: int = 50):
    """Dynamically adjust worksheet column widths based on content."""
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val_str = str(cell.value or "")
            lines = val_str.split("\n")
            line_len = max(len(line) for line in lines) if lines else 0
            if line_len > max_len:
                max_len = line_len
        calculated_width = max(max_len + 3, min_width)
        ws.column_dimensions[col_letter].width = min(calculated_width, max_width)


def export_report_to_excel(
    dataset: ReportDataset,
    output_path: Union[str, Path],
    log_callback: Optional[Callable[[str], None]] = None,
) -> Path:
    """
    Builds the formatted 2-sheet plain-text Excel report workbook.
    
    Sheet 1: 'Attendance Matrix' (Incident Number, Incident Type, Date, Personnel...)
    Sheet 2: 'Incident Types & Apparatus' (2 columns: Type/Apparatus, n/N (n%))
    """
    def _log(msg: str):
        if log_callback:
            log_callback(msg)

    out_file = Path(output_path).expanduser().resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    _log("Creating plain-text Excel workbook with two sheets...")
    wb = openpyxl.Workbook()

    # =========================================================================
    # --- Sheet 1: Attendance Matrix (Plain Text) ---
    # =========================================================================
    _log(f"Writing Sheet 1: Master Attendance Matrix ({len(dataset.incidents)} incidents x {len(dataset.roster)} personnel)...")
    ws1 = wb.active
    ws1.title = "Attendance Matrix"
    ws1.views.sheetView[0].showGridLines = True

    # Row 1: Headers: Number, Type, Date, followed by roster
    headers_ws1 = ["Incident Number", "Incident Type", "Date"] + dataset.roster
    ws1.append(headers_ws1)

    for col_idx in range(1, len(headers_ws1) + 1):
        cell = ws1.cell(row=1, column=col_idx)
        cell.font = BOLD_FONT
        cell.alignment = ALIGN_CENTER if col_idx > 3 else ALIGN_LEFT
        cell.border = THIN_BORDER
    ws1.row_dimensions[1].height = 24

    # Data Rows: Incidents
    current_row = 2
    for inc in dataset.incidents:
        clean_date = _format_cell_date(inc.incident_date or "")
        row_vals = [inc.incident_number, inc.incident_type, clean_date]
        matrix_row = dataset.attendance_matrix.get(inc.incident_number, {})
        rep_row = dataset.report_attendance_matrix.get(inc.incident_number, {})
        rad_row = dataset.radio_attendance_matrix.get(inc.incident_number, {})

        for member in dataset.roster:
            in_rep = rep_row.get(member, False)
            in_rad = rad_row.get(member, False)
            if in_rep and in_rad:
                indicator = "XR"
            elif in_rep:
                indicator = "X"
            elif in_rad:
                indicator = "R"
            elif matrix_row.get(member, False):
                indicator = "X"
            else:
                indicator = ""
            row_vals.append(indicator)

        ws1.append(row_vals)
        ws1.row_dimensions[current_row].height = 20

        # Plain text cells
        for col_idx in range(1, len(row_vals) + 1):
            cell = ws1.cell(row=current_row, column=col_idx)
            cell.border = THIN_BORDER
            cell.font = REGULAR_FONT
            if col_idx == 1:
                cell.alignment = ALIGN_CENTER
            elif col_idx in (2, 3):
                cell.alignment = ALIGN_LEFT
            else:
                cell.alignment = ALIGN_CENTER
        current_row += 1

    # Summary Row: Row M+1
    summary_row_vals = [
        "Total Calls Made",
        f"Total Incidents: {dataset.total_incidents}",
        "",  # Blank under Date column
    ]
    for member in dataset.roster:
        summary = dataset.personnel_summaries.get(member)
        formatted = summary.formatted_ratio if summary else f"0/{dataset.total_incidents} (0.0%)"
        summary_row_vals.append(formatted)

    ws1.append(summary_row_vals)
    summary_row_idx = current_row
    ws1.row_dimensions[summary_row_idx].height = 22

    for col_idx in range(1, len(summary_row_vals) + 1):
        cell = ws1.cell(row=summary_row_idx, column=col_idx)
        cell.font = BOLD_FONT
        cell.border = SUMMARY_BORDER
        cell.alignment = ALIGN_CENTER if col_idx > 3 else ALIGN_LEFT

    # Freeze Panes: Freeze Row 1 and Columns A, B, C (cell D2)
    ws1.freeze_panes = "D2"
    _auto_fit_columns(ws1, min_width=12, max_width=45)

    # =========================================================================
    # --- Sheet 2: Incident Types & Apparatus (2 Columns) ---
    # =========================================================================
    _log(f"Writing Sheet 2: Section 1 (Incident Types Breakdown, {len(dataset.type_summaries)} categories)...")
    ws2 = wb.create_sheet(title="Incident Types & Apparatus")
    ws2.views.sheetView[0].showGridLines = True

    # --- Section 1: Incident Types Breakdown ---
    ws2.append(["INCIDENT TYPES BREAKDOWN", ""])
    ws2.cell(row=1, column=1).font = BOLD_FONT

    headers_types = ["Incident Type", "Total Calls Made (%)"]
    ws2.append(headers_types)
    for col_idx in range(1, 3):
        cell = ws2.cell(row=2, column=col_idx)
        cell.font = BOLD_FONT
        cell.alignment = ALIGN_RIGHT if col_idx == 2 else ALIGN_LEFT
        cell.border = THIN_BORDER
    ws2.row_dimensions[2].height = 22

    current_row_ws2 = 3
    for item in dataset.type_summaries:
        ratio_str = f"{item.count}/{dataset.total_incidents} ({item.percentage:.1f}%)"
        row_vals = [item.incident_type, ratio_str]
        ws2.append(row_vals)
        ws2.row_dimensions[current_row_ws2].height = 20

        for col_idx in range(1, 3):
            cell = ws2.cell(row=current_row_ws2, column=col_idx)
            cell.border = THIN_BORDER
            cell.font = REGULAR_FONT
            cell.alignment = ALIGN_RIGHT if col_idx == 2 else ALIGN_LEFT
        current_row_ws2 += 1

    # Total row for incident types
    total_types_count = sum(t.count for t in dataset.type_summaries)
    summary_types_vals = [
        "Total Incidents",
        f"{total_types_count}/{dataset.total_incidents} (100.0%)",
    ]
    ws2.append(summary_types_vals)
    summary_types_idx = current_row_ws2
    ws2.row_dimensions[summary_types_idx].height = 22

    for col_idx in range(1, 3):
        cell = ws2.cell(row=summary_types_idx, column=col_idx)
        cell.font = BOLD_FONT
        cell.border = SUMMARY_BORDER
        cell.alignment = ALIGN_RIGHT if col_idx == 2 else ALIGN_LEFT
    current_row_ws2 += 1

    # Spacer row
    ws2.append([])
    current_row_ws2 += 1

    # --- Section 2: Apparatus Responses Breakdown ---
    _log(f"Writing Sheet 2: Section 2 (Apparatus Breakdown, {len(dataset.apparatus_summaries)} units)...")
    ws2.append(["APPARATUS / RESOURCE BREAKDOWN", ""])
    ws2.cell(row=current_row_ws2, column=1).font = BOLD_FONT
    current_row_ws2 += 1

    headers_apparatus = ["Apparatus / Resource", "Total Calls Made (%)"]
    ws2.append(headers_apparatus)
    for col_idx in range(1, 3):
        cell = ws2.cell(row=current_row_ws2, column=col_idx)
        cell.font = BOLD_FONT
        cell.alignment = ALIGN_RIGHT if col_idx == 2 else ALIGN_LEFT
        cell.border = THIN_BORDER
    ws2.row_dimensions[current_row_ws2].height = 22
    current_row_ws2 += 1

    for app in dataset.apparatus_summaries:
        ratio_str = f"{app.count}/{dataset.total_incidents} ({app.percentage:.1f}%)"
        row_vals = [app.apparatus_name, ratio_str]
        ws2.append(row_vals)
        ws2.row_dimensions[current_row_ws2].height = 20

        for col_idx in range(1, 3):
            cell = ws2.cell(row=current_row_ws2, column=col_idx)
            cell.border = THIN_BORDER
            cell.font = REGULAR_FONT
            cell.alignment = ALIGN_RIGHT if col_idx == 2 else ALIGN_LEFT
        current_row_ws2 += 1

    # --- Section 3: Other / Inactive Reports (if any) ---
    if dataset.inactive_incidents:
        _log(f"Writing Sheet 2: Section 3 (Other / Inactive Reports Audit Log, {len(dataset.inactive_incidents)} records)...")
        ws2.append([])
        current_row_ws2 += 1

        ws2.append(["OTHER / INACTIVE REPORTS", ""])
        ws2.cell(row=current_row_ws2, column=1).font = BOLD_FONT
        current_row_ws2 += 1

        headers_inactive = ["Incident Number (Status)", "Date / Description"]
        ws2.append(headers_inactive)
        for col_idx in range(1, 3):
            cell = ws2.cell(row=current_row_ws2, column=col_idx)
            cell.font = BOLD_FONT
            cell.alignment = ALIGN_LEFT
            cell.border = THIN_BORDER
        ws2.row_dimensions[current_row_ws2].height = 22
        current_row_ws2 += 1

        for inc in dataset.inactive_incidents:
            clean_date = _format_cell_date(inc.incident_date or "")
            label = f"{inc.incident_number} ({inc.status or 'INACTIVE'})"
            desc = clean_date if clean_date else "No date recorded"
            if inc.incident_type and inc.incident_type != "Unknown Incident Type":
                desc += f" - {inc.incident_type}"
            else:
                desc += " - Draft / No crew assigned"

            row_vals = [label, desc]
            ws2.append(row_vals)
            ws2.row_dimensions[current_row_ws2].height = 20

            for col_idx in range(1, 3):
                cell = ws2.cell(row=current_row_ws2, column=col_idx)
                cell.border = THIN_BORDER
                cell.font = REGULAR_FONT
                cell.alignment = ALIGN_LEFT
            current_row_ws2 += 1

    ws2.freeze_panes = "A3"
    _auto_fit_columns(ws2, min_width=18, max_width=60)

    # =========================================================================
    # --- Sheet 3: CAD Notes & Radio Audit ---
    # =========================================================================
    _log("Writing Sheet 3: CAD Notes & Radio Audit...")
    ws3 = wb.create_sheet(title="CAD Notes & Radio Audit")
    ws3.views.sheetView[0].showGridLines = True

    # --- Section 1: Incident CAD & Radio Breakdown ---
    ws3.append(["INCIDENT CAD & RADIO BREAKDOWN", ""])
    ws3.cell(row=1, column=1).font = BOLD_FONT

    headers_cad = [
        "Incident Number",
        "Date",
        "Personnel on Report",
        "Radio Marks Found",
        "Mapped Members",
        "CAD Notes Snippet",
    ]
    ws3.append(headers_cad)
    for col_idx in range(1, len(headers_cad) + 1):
        cell = ws3.cell(row=2, column=col_idx)
        cell.font = BOLD_FONT
        cell.alignment = ALIGN_LEFT
        cell.border = THIN_BORDER
    ws3.row_dimensions[2].height = 22

    current_row_ws3 = 3
    for inc in dataset.incidents:
        clean_date = _format_cell_date(inc.incident_date or "")
        rep_str = ", ".join(inc.get_normalized_responders()) if inc.responders else "None"
        marks_str = ", ".join(inc.radio_markups_found) if inc.radio_markups_found else "None"
        mapped_str = ", ".join(inc.radio_responders) if inc.radio_responders else "None"
        raw_cad = inc.cad_notes or "No CAD notes recorded"
        first_snippet = raw_cad.strip().replace("\r\n", " ").replace("\n", " ")
        if len(first_snippet) > 150:
            first_snippet = first_snippet[:147] + "..."

        row_vals = [inc.incident_number, clean_date, rep_str, marks_str, mapped_str, first_snippet]
        ws3.append(row_vals)
        ws3.row_dimensions[current_row_ws3].height = 20

        for col_idx in range(1, len(row_vals) + 1):
            cell = ws3.cell(row=current_row_ws3, column=col_idx)
            cell.border = THIN_BORDER
            cell.font = REGULAR_FONT
            cell.alignment = ALIGN_CENTER if col_idx == 1 else ALIGN_LEFT
        current_row_ws3 += 1

    # Spacer row
    ws3.append([])
    current_row_ws3 += 1

    # --- Section 2: Unmapped Call Signs Audit Table ---
    ws3.append(["UNMAPPED CALL SIGNS AUDIT LOG", ""])
    ws3.cell(row=current_row_ws3, column=1).font = BOLD_FONT
    current_row_ws3 += 1

    headers_unmapped = [
        "Call Sign / Token",
        "Incident Number",
        "Date",
        "CAD Remark Snippet",
        "Reason / Status",
    ]
    ws3.append(headers_unmapped)
    for col_idx in range(1, len(headers_unmapped) + 1):
        cell = ws3.cell(row=current_row_ws3, column=col_idx)
        cell.font = BOLD_FONT
        cell.alignment = ALIGN_LEFT
        cell.border = THIN_BORDER
    ws3.row_dimensions[current_row_ws3].height = 22
    current_row_ws3 += 1

    if dataset.all_unmapped_cad_marks:
        for mark in dataset.all_unmapped_cad_marks:
            clean_date = _format_cell_date(mark.incident_date or "")
            row_vals = [mark.token, mark.incident_number, clean_date, mark.snippet, mark.reason]
            ws3.append(row_vals)
            ws3.row_dimensions[current_row_ws3].height = 20
            for col_idx in range(1, len(row_vals) + 1):
                cell = ws3.cell(row=current_row_ws3, column=col_idx)
                cell.border = THIN_BORDER
                cell.font = REGULAR_FONT
                cell.alignment = ALIGN_CENTER if col_idx <= 2 else ALIGN_LEFT
            current_row_ws3 += 1
    else:
        row_vals = ["None detected", "-", "-", "All CAD radio marks mapped to active department members", "Verified"]
        ws3.append(row_vals)
        ws3.row_dimensions[current_row_ws3].height = 20
        for col_idx in range(1, len(row_vals) + 1):
            cell = ws3.cell(row=current_row_ws3, column=col_idx)
            cell.border = THIN_BORDER
            cell.font = REGULAR_FONT
            cell.alignment = ALIGN_LEFT
        current_row_ws3 += 1

    # Spacer row
    ws3.append([])
    current_row_ws3 += 1

    # --- Section 3: Unmapped Call Signs Frequency Summary ---
    ws3.append(["UNMAPPED CALL SIGNS FREQUENCY SUMMARY", ""])
    ws3.cell(row=current_row_ws3, column=1).font = BOLD_FONT
    current_row_ws3 += 1

    headers_freq = ["Call Sign", "Total Occurrences", "Suggested Action"]
    ws3.append(headers_freq)
    for col_idx in range(1, len(headers_freq) + 1):
        cell = ws3.cell(row=current_row_ws3, column=col_idx)
        cell.font = BOLD_FONT
        cell.alignment = ALIGN_RIGHT if col_idx == 2 else ALIGN_LEFT
        cell.border = THIN_BORDER
    ws3.row_dimensions[current_row_ws3].height = 22
    current_row_ws3 += 1

    if dataset.unmapped_cad_frequency:
        sorted_freq = sorted(dataset.unmapped_cad_frequency.items(), key=lambda x: (-x[1], x[0]))
        for token, count in sorted_freq:
            action = "Verify if new member; add to Member Manager"
            row_vals = [token, count, action]
            ws3.append(row_vals)
            ws3.row_dimensions[current_row_ws3].height = 20
            for col_idx in range(1, len(row_vals) + 1):
                cell = ws3.cell(row=current_row_ws3, column=col_idx)
                cell.border = THIN_BORDER
                cell.font = REGULAR_FONT
                cell.alignment = ALIGN_RIGHT if col_idx == 2 else ALIGN_LEFT
            current_row_ws3 += 1
    else:
        row_vals = ["None detected", 0, "No action required"]
        ws3.append(row_vals)
        ws3.row_dimensions[current_row_ws3].height = 20
        for col_idx in range(1, len(row_vals) + 1):
            cell = ws3.cell(row=current_row_ws3, column=col_idx)
            cell.border = THIN_BORDER
            cell.font = REGULAR_FONT
            cell.alignment = ALIGN_RIGHT if col_idx == 2 else ALIGN_LEFT
        current_row_ws3 += 1

    ws3.freeze_panes = "A3"
    _auto_fit_columns(ws3, min_width=14, max_width=60)

    # Save to disk
    _log(f"Saving Excel workbook to {out_file}...")
    try:
        wb.save(str(out_file))
    except PermissionError:
        # File is likely open in Excel/LibreOffice. Auto-fallback to avoid discarding scraped data.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback_name = f"{out_file.stem}_{timestamp}{out_file.suffix}"
        fallback_path = out_file.parent / fallback_name
        _log(f"Notice: '{out_file.name}' is open or locked. Saving to fallback '{fallback_name}'...")
        try:
            wb.save(str(fallback_path))
            out_file = fallback_path
        except Exception as inner_e:
            raise PermissionError(
                f"Cannot save to '{out_file}' or fallback '{fallback_path}'. "
                "Please close any open spreadsheets and try again."
            ) from inner_e
    _log("Workbook saved successfully.")
    return out_file
