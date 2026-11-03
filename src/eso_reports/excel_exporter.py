"""
Excel report generation module using openpyxl.
Produces standardized ESO Report.xlsx with two worksheets:
- Sheet 1: 'Call Percentage' (Rows: Unit #, Name, followed by #[last 3 digits of call number] for each call)
- Sheet 2: 'Other' (Top tables: Incident Types, Apparatus, Other with questionable CAD marks/inactive records;
           followed by CAD audit logs for debugging)
"""

from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Union
import openpyxl
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

from .models import ReportDataset

# Clean Plain Text Styles (Arial font across all text)
REGULAR_FONT = Font(name="Arial", size=11)
BOLD_FONT = Font(name="Arial", size=11, bold=True)

THIN_BORDER_SIDE = Side(style="thin", color="000000")
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


def format_call_header(incident_number: str) -> str:
    """Extracts last three digits of incident number prefixed with '#' e.g. '#356'."""
    clean = str(incident_number).strip()
    digits = re.findall(r"\d+", clean)
    if digits:
        all_digits = "".join(digits)
        last_three = all_digits[-3:] if len(all_digits) >= 3 else all_digits.zfill(3)
        return f"#{last_three}"
    suffix = clean[-3:] if len(clean) >= 3 else clean
    return f"#{suffix}"


def _apply_box_border(
    ws,
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
    border_style: str = "medium",
    color: str = "000000",
):
    """Applies a thicker outer border around a rectangular table while preserving inner borders."""
    thick_side = Side(style=border_style, color=color)
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            cell = ws.cell(row=r, column=c)
            curr = cell.border or THIN_BORDER
            top = thick_side if r == min_row else curr.top
            bottom = thick_side if r == max_row else curr.bottom
            left = thick_side if c == min_col else curr.left
            right = thick_side if c == max_col else curr.right
            cell.border = Border(top=top, bottom=bottom, left=left, right=right)


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
    Builds the standardized 2-sheet plain-text Excel report workbook.
    
    Sheet 1: 'Call Percentage'
      - Rows: Unit #, Name, #[last three digits of call number] for each call.
      - Frozen columns: Unit # (A) and Name (B).
      - Frozen row: Top row (1).
      - Unit # column bolded.
      - Outlines on every box.
      - Print setup repeats columns A and B on multi-page prints.
    
    Sheet 2: 'Other'
      - Top row tables (side-by-side):
        - Incident Types (Cols A-B)
        - Apparatus (Cols D-E, 1 column space from Incident Types)
        - Other (Cols H-I, 2 column space from Apparatus; contains questionable CAD marks and inactive reports)
        - Outer borders around each top table.
      - No frozen top rows.
      - Debugging sections below top tables (Incident CAD breakdown, unmapped audit log, frequency summary).
    """
    def _log(msg: str):
        if log_callback:
            log_callback(msg)

    out_file = Path(output_path).expanduser().resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    _log("Creating plain-text Excel workbook with two sheets...")
    wb = openpyxl.Workbook()

    # =========================================================================
    # --- Sheet 1: Call Percentage ---
    # =========================================================================
    _log(f"Writing Sheet 1: Call Percentage ({len(dataset.unit_roster)} units x {len(dataset.incidents)} calls)...")
    ws1 = wb.active
    ws1.title = "Call Percentage"
    ws1.views.sheetView[0].showGridLines = True

    # Row 1: Headers: Unit #, Name, followed by #[last three digits] for each call
    call_headers = [format_call_header(inc.incident_number) for inc in dataset.incidents]
    headers_ws1 = ["Unit #", "Name"] + call_headers
    ws1.append(headers_ws1)

    for col_idx in range(1, len(headers_ws1) + 1):
        cell = ws1.cell(row=1, column=col_idx)
        cell.font = BOLD_FONT
        cell.alignment = ALIGN_LEFT if col_idx == 2 else ALIGN_CENTER
        cell.border = THIN_BORDER
    ws1.row_dimensions[1].height = 24

    # Data Rows: Unit numbers (always includes 1510 - 1564)
    current_row = 2
    for unit_num in dataset.unit_roster:
        name_val = dataset.unit_to_name.get(unit_num, "")
        row_vals = [unit_num, name_val]

        for inc in dataset.incidents:
            attended = dataset.unit_attendance_matrix.get(inc.incident_number, {}).get(unit_num, False)
            row_vals.append("X" if attended else "")

        ws1.append(row_vals)
        ws1.row_dimensions[current_row].height = 20

        # Style data cells
        for col_idx in range(1, len(row_vals) + 1):
            cell = ws1.cell(row=current_row, column=col_idx)
            cell.border = THIN_BORDER
            if col_idx == 1:
                # The Unit # column should be bolded
                cell.font = BOLD_FONT
                cell.alignment = ALIGN_CENTER
            elif col_idx == 2:
                cell.font = REGULAR_FONT
                cell.alignment = ALIGN_LEFT
            else:
                cell.font = REGULAR_FONT
                cell.alignment = ALIGN_CENTER
        current_row += 1

    # Freeze Panes: Freeze Unit # and Name columns (A & B) and Top Row (Row 1) -> cell C2
    ws1.freeze_panes = "C2"

    # Multi-page print settings: automatically repeat columns A & B on second printed page
    ws1.print_title_cols = "A:B"
    ws1.print_title_rows = "1:1"

    # Column widths for Sheet 1
    ws1.column_dimensions["A"].width = 12
    max_name_len = max([len(dataset.unit_to_name.get(u, "")) for u in dataset.unit_roster] + [len("Name")])
    ws1.column_dimensions["B"].width = max(max_name_len + 4, 22)
    for c_idx in range(3, len(headers_ws1) + 1):
        c_letter = get_column_letter(c_idx)
        ws1.column_dimensions[c_letter].width = 8

    # =========================================================================
    # --- Sheet 2: Other ---
    # =========================================================================
    _log("Writing Sheet 2: Other (Incident Types, Apparatus, Other & Debug Audit)...")
    ws2 = wb.create_sheet(title="Other")
    ws2.views.sheetView[0].showGridLines = True
    # Explicitly ensure no frozen panes on Sheet 2
    ws2.freeze_panes = None

    # --- Top Table 1: Incident Types (Columns A & B, Rows 1 to N) ---
    ws2.cell(row=1, column=1, value="Incident Type").font = BOLD_FONT
    ws2.cell(row=1, column=1).alignment = ALIGN_LEFT
    ws2.cell(row=1, column=1).border = THIN_BORDER

    ws2.cell(row=1, column=2, value="Total Calls Made (%)").font = BOLD_FONT
    ws2.cell(row=1, column=2).alignment = ALIGN_RIGHT
    ws2.cell(row=1, column=2).border = THIN_BORDER
    ws2.row_dimensions[1].height = 22

    t1_row = 2
    for item in dataset.type_summaries:
        ratio_str = f"{item.count}/{dataset.total_incidents} ({item.percentage:.1f}%)"
        ws2.cell(row=t1_row, column=1, value=item.incident_type).font = REGULAR_FONT
        ws2.cell(row=t1_row, column=1).alignment = ALIGN_LEFT
        ws2.cell(row=t1_row, column=1).border = THIN_BORDER

        ws2.cell(row=t1_row, column=2, value=ratio_str).font = REGULAR_FONT
        ws2.cell(row=t1_row, column=2).alignment = ALIGN_RIGHT
        ws2.cell(row=t1_row, column=2).border = THIN_BORDER
        ws2.row_dimensions[t1_row].height = 20
        t1_row += 1

    total_types_count = sum(t.count for t in dataset.type_summaries)
    ws2.cell(row=t1_row, column=1, value="Total Incidents").font = BOLD_FONT
    ws2.cell(row=t1_row, column=1).alignment = ALIGN_LEFT
    ws2.cell(row=t1_row, column=1).border = SUMMARY_BORDER

    ws2.cell(row=t1_row, column=2, value=f"{total_types_count}/{dataset.total_incidents} (100.0%)").font = BOLD_FONT
    ws2.cell(row=t1_row, column=2).alignment = ALIGN_RIGHT
    ws2.cell(row=t1_row, column=2).border = SUMMARY_BORDER
    ws2.row_dimensions[t1_row].height = 22
    t1_last_row = t1_row

    # Outer border around Table 1
    _apply_box_border(ws2, min_row=1, max_row=t1_last_row, min_col=1, max_col=2)

    # Column C: Spacer between Incident Types and Apparatus
    ws2.column_dimensions["C"].width = 4

    # --- Top Table 2: Apparatus (Columns D & E, Rows 1 to M) ---
    ws2.cell(row=1, column=4, value="Apparatus").font = BOLD_FONT
    ws2.cell(row=1, column=4).alignment = ALIGN_LEFT
    ws2.cell(row=1, column=4).border = THIN_BORDER

    ws2.cell(row=1, column=5, value="Total Calls Made (%)").font = BOLD_FONT
    ws2.cell(row=1, column=5).alignment = ALIGN_RIGHT
    ws2.cell(row=1, column=5).border = THIN_BORDER

    t2_row = 2
    if dataset.apparatus_summaries:
        for app in dataset.apparatus_summaries:
            ratio_str = f"{app.count}/{dataset.total_incidents} ({app.percentage:.1f}%)"
            ws2.cell(row=t2_row, column=4, value=app.apparatus_name).font = REGULAR_FONT
            ws2.cell(row=t2_row, column=4).alignment = ALIGN_LEFT
            ws2.cell(row=t2_row, column=4).border = THIN_BORDER

            ws2.cell(row=t2_row, column=5, value=ratio_str).font = REGULAR_FONT
            ws2.cell(row=t2_row, column=5).alignment = ALIGN_RIGHT
            ws2.cell(row=t2_row, column=5).border = THIN_BORDER
            ws2.row_dimensions[t2_row].height = 20
            t2_row += 1
        t2_last_row = t2_row - 1
    else:
        ws2.cell(row=2, column=4, value="None recorded").font = REGULAR_FONT
        ws2.cell(row=2, column=4).alignment = ALIGN_LEFT
        ws2.cell(row=2, column=4).border = THIN_BORDER

        ws2.cell(row=2, column=5, value="0/0 (0.0%)").font = REGULAR_FONT
        ws2.cell(row=2, column=5).alignment = ALIGN_RIGHT
        ws2.cell(row=2, column=5).border = THIN_BORDER
        t2_last_row = 2

    # Outer border around Table 2
    _apply_box_border(ws2, min_row=1, max_row=t2_last_row, min_col=4, max_col=5)

    # Columns F & G: Two spacer columns between Apparatus and Other
    ws2.column_dimensions["F"].width = 4
    ws2.column_dimensions["G"].width = 4

    # --- Top Table 3: Other (Columns H & I, Rows 1 to K) ---
    ws2.cell(row=1, column=8, value="Other").font = BOLD_FONT
    ws2.cell(row=1, column=8).alignment = ALIGN_LEFT
    ws2.cell(row=1, column=8).border = THIN_BORDER

    ws2.cell(row=1, column=9, value="Description").font = BOLD_FONT
    ws2.cell(row=1, column=9).alignment = ALIGN_LEFT
    ws2.cell(row=1, column=9).border = THIN_BORDER

    t3_row = 2
    incident_by_num = {inc.incident_number: inc for inc in dataset.incidents}

    # 1. Questionable unit numbers from CAD notes
    # Formatted description: "from [call number] [date] [time] [incident type]"
    if dataset.all_unmapped_cad_marks:
        for mark in dataset.all_unmapped_cad_marks:
            inc = incident_by_num.get(mark.incident_number)
            clean_dt = _format_cell_date(mark.incident_date or (inc.incident_date if inc else "") or "")
            itype = (inc.incident_type if inc else "") or "Unknown Incident Type"
            desc = f"from {mark.incident_number}"
            if clean_dt:
                desc += f" {clean_dt}"
            if itype and itype != "Unknown Incident Type":
                desc += f" - {itype}"

            ws2.cell(row=t3_row, column=8, value=mark.token).font = REGULAR_FONT
            ws2.cell(row=t3_row, column=8).alignment = ALIGN_LEFT
            ws2.cell(row=t3_row, column=8).border = THIN_BORDER

            ws2.cell(row=t3_row, column=9, value=desc).font = REGULAR_FONT
            ws2.cell(row=t3_row, column=9).alignment = ALIGN_LEFT
            ws2.cell(row=t3_row, column=9).border = THIN_BORDER
            ws2.row_dimensions[t3_row].height = 20
            t3_row += 1

    # 2. Inactive / Draft reports
    if dataset.inactive_incidents:
        for inc in dataset.inactive_incidents:
            clean_date = _format_cell_date(inc.incident_date or "")
            label = f"{inc.incident_number} ({inc.status or 'INACTIVE'})"
            desc = clean_date if clean_date else "No date recorded"
            if inc.incident_type and inc.incident_type != "Unknown Incident Type":
                desc += f" - {inc.incident_type}"
            else:
                desc += " - Draft / No crew assigned"

            ws2.cell(row=t3_row, column=8, value=label).font = REGULAR_FONT
            ws2.cell(row=t3_row, column=8).alignment = ALIGN_LEFT
            ws2.cell(row=t3_row, column=8).border = THIN_BORDER

            ws2.cell(row=t3_row, column=9, value=desc).font = REGULAR_FONT
            ws2.cell(row=t3_row, column=9).alignment = ALIGN_LEFT
            ws2.cell(row=t3_row, column=9).border = THIN_BORDER
            ws2.row_dimensions[t3_row].height = 20
            t3_row += 1

    # Placeholder if no questionable marks and no inactive reports
    if t3_row == 2:
        ws2.cell(row=2, column=8, value="None detected").font = REGULAR_FONT
        ws2.cell(row=2, column=8).alignment = ALIGN_LEFT
        ws2.cell(row=2, column=8).border = THIN_BORDER

        ws2.cell(row=2, column=9, value="All records and CAD radio marks verified").font = REGULAR_FONT
        ws2.cell(row=2, column=9).alignment = ALIGN_LEFT
        ws2.cell(row=2, column=9).border = THIN_BORDER
        t3_last_row = 2
    else:
        t3_last_row = t3_row - 1

    # Outer border around Table 3
    _apply_box_border(ws2, min_row=1, max_row=t3_last_row, min_col=8, max_col=9)

    # Column widths for top tables
    ws2.column_dimensions["A"].width = 24
    ws2.column_dimensions["B"].width = 22
    ws2.column_dimensions["D"].width = 22
    ws2.column_dimensions["E"].width = 22
    ws2.column_dimensions["H"].width = 20
    ws2.column_dimensions["I"].width = 52

    # =========================================================================
    # --- Debugging Tables (Moved from former Sheet 3 below top tables) ---
    # =========================================================================
    max_top_row = max(t1_last_row, t2_last_row, t3_last_row)
    curr_debug_row = max_top_row + 3

    # Section 1: Incident CAD & Radio Breakdown
    ws2.cell(row=curr_debug_row, column=1, value="INCIDENT CAD & RADIO BREAKDOWN").font = BOLD_FONT
    curr_debug_row += 1

    headers_cad = [
        "Incident Number",
        "Date",
        "Personnel on Report",
        "Radio Marks Found",
        "Mapped Members",
        "CAD Notes Snippet",
    ]
    for col_idx, h in enumerate(headers_cad, 1):
        c = ws2.cell(row=curr_debug_row, column=col_idx, value=h)
        c.font = BOLD_FONT
        c.alignment = ALIGN_LEFT
        c.border = THIN_BORDER
    ws2.row_dimensions[curr_debug_row].height = 22
    curr_debug_row += 1

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
        for col_idx, val in enumerate(row_vals, 1):
            c = ws2.cell(row=curr_debug_row, column=col_idx, value=val)
            c.font = REGULAR_FONT
            c.border = THIN_BORDER
            c.alignment = ALIGN_CENTER if col_idx == 1 else ALIGN_LEFT
        ws2.row_dimensions[curr_debug_row].height = 20
        curr_debug_row += 1

    curr_debug_row += 1  # Spacer row

    # Section 2: Unmapped Call Signs Audit Table
    ws2.cell(row=curr_debug_row, column=1, value="UNMAPPED CALL SIGNS AUDIT LOG").font = BOLD_FONT
    curr_debug_row += 1

    headers_unmapped = [
        "Call Sign / Token",
        "Incident Number",
        "Date",
        "CAD Remark Snippet",
        "Reason / Status",
    ]
    for col_idx, h in enumerate(headers_unmapped, 1):
        c = ws2.cell(row=curr_debug_row, column=col_idx, value=h)
        c.font = BOLD_FONT
        c.alignment = ALIGN_LEFT
        c.border = THIN_BORDER
    ws2.row_dimensions[curr_debug_row].height = 22
    curr_debug_row += 1

    if dataset.all_unmapped_cad_marks:
        for mark in dataset.all_unmapped_cad_marks:
            clean_date = _format_cell_date(mark.incident_date or "")
            row_vals = [mark.token, mark.incident_number, clean_date, mark.snippet, mark.reason]
            for col_idx, val in enumerate(row_vals, 1):
                c = ws2.cell(row=curr_debug_row, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.border = THIN_BORDER
                c.alignment = ALIGN_CENTER if col_idx <= 2 else ALIGN_LEFT
            ws2.row_dimensions[curr_debug_row].height = 20
            curr_debug_row += 1
    else:
        row_vals = ["None detected", "-", "-", "All CAD radio marks mapped to active department members", "Verified"]
        for col_idx, val in enumerate(row_vals, 1):
            c = ws2.cell(row=curr_debug_row, column=col_idx, value=val)
            c.font = REGULAR_FONT
            c.border = THIN_BORDER
            c.alignment = ALIGN_LEFT
        ws2.row_dimensions[curr_debug_row].height = 20
        curr_debug_row += 1

    curr_debug_row += 1  # Spacer row

    # Section 3: Unmapped Call Signs Frequency Summary
    ws2.cell(row=curr_debug_row, column=1, value="UNMAPPED CALL SIGNS FREQUENCY SUMMARY").font = BOLD_FONT
    curr_debug_row += 1

    headers_freq = ["Call Sign", "Total Occurrences", "Suggested Action"]
    for col_idx, h in enumerate(headers_freq, 1):
        c = ws2.cell(row=curr_debug_row, column=col_idx, value=h)
        c.font = BOLD_FONT
        c.alignment = ALIGN_RIGHT if col_idx == 2 else ALIGN_LEFT
        c.border = THIN_BORDER
    ws2.row_dimensions[curr_debug_row].height = 22
    curr_debug_row += 1

    if dataset.unmapped_cad_frequency:
        sorted_freq = sorted(dataset.unmapped_cad_frequency.items(), key=lambda x: (-x[1], x[0]))
        for token, count in sorted_freq:
            action = "Verify if new member; add to Member Manager"
            row_vals = [token, count, action]
            for col_idx, val in enumerate(row_vals, 1):
                c = ws2.cell(row=curr_debug_row, column=col_idx, value=val)
                c.font = REGULAR_FONT
                c.border = THIN_BORDER
                c.alignment = ALIGN_RIGHT if col_idx == 2 else ALIGN_LEFT
            ws2.row_dimensions[curr_debug_row].height = 20
            curr_debug_row += 1
    else:
        row_vals = ["None detected", 0, "No action required"]
        for col_idx, val in enumerate(row_vals, 1):
            c = ws2.cell(row=curr_debug_row, column=col_idx, value=val)
            c.font = REGULAR_FONT
            c.border = THIN_BORDER
            c.alignment = ALIGN_RIGHT if col_idx == 2 else ALIGN_LEFT
        ws2.row_dimensions[curr_debug_row].height = 20
        curr_debug_row += 1

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
