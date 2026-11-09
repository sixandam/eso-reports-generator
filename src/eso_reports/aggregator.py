"""
Data transformation and metrics aggregation engine for ESO Suite reports.
Calculates Attendance Matrix, Incident Types distribution, and Apparatus statistics.
"""

from __future__ import annotations
from collections import Counter
from typing import Callable, Dict, List, Optional, Set
from .models import (
    Incident,
    AttendanceSummary,
    IncidentTypeSummary,
    ApparatusSummary,
    ReportDataset,
    Member,
    UnmappedCADMark,
    CADLegendEntry,
    normalize_personnel_name,
    format_display_name,
    extract_name_and_badge,
)
from .member_manager import load_members
from .cad_parser import CADParser, extract_unit_from_token


def normalize_apparatus_name(raw_name: str) -> str:
    """Standardizes apparatus designations (e.g. 'engine 15' -> 'Engine 15', 'pov' -> 'POV')."""
    clean = " ".join(raw_name.strip().split())
    if not clean:
        return ""
    if clean.upper() in ("POV", "EMS", "ATV", "UTV"):
        return clean.upper()
    tokens = clean.split()
    formatted = []
    for t in tokens:
        if t.upper() in ("POV", "EMS", "ATV", "UTV"):
            formatted.append(t.upper())
        elif t.isdigit() or any(c.isdigit() for c in t):
            formatted.append(t)
        else:
            formatted.append(t.capitalize())
    return " ".join(formatted)


def build_report_dataset(
    incidents: List[Incident],
    known_roster: Optional[List[str]] = None,
    members_db: Optional[List[Member]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> ReportDataset:
    """
    Transforms a list of incidents into structured report data.

    Calculates:
    - Roster list sorted alphabetically, including active zero-call members.
    - Attendance matrices: report-only, radio-only (CAD), and combined.
    - Multi-source cell indicators and attendance metrics per member.
    - Incident type distribution and apparatus distribution.
    - Comprehensive CAD and radio audit logs and frequency counters.
    """
    def _log(msg: str):
        if log_callback:
            log_callback(msg)

    _log("Normalizing personnel names and building department roster...")
    # 0. Segregate active incidents from inactive/discarded placeholder records
    active_incidents = [inc for inc in incidents if (inc.status or "ACTIVE").upper() != "INACTIVE"]
    inactive_incidents = [inc for inc in incidents if (inc.status or "ACTIVE").upper() == "INACTIVE"]

    # 1. Resolve department members and active roster
    effective_members = members_db
    roster_set: Set[str] = set()

    # Add active members from members_db (ensures zero-call members appear on roster)
    if effective_members:
        for m in effective_members:
            if m.active and m.name:
                norm = normalize_personnel_name(m.name) or m.name
                roster_set.add(norm)

    if known_roster:
        for name in known_roster:
            norm = normalize_personnel_name(name)
            if norm:
                roster_set.add(norm)

    # 2. Parse/re-parse CAD notes with current members if available
    cad_parser = CADParser(effective_members) if effective_members else None

    all_unmapped_cad_marks: List[UnmappedCADMark] = []
    unmapped_cad_frequency: Counter = Counter()

    # Collect responders from active incident records (Report + Radio)
    incident_report_map: Dict[str, Set[str]] = {}
    incident_radio_map: Dict[str, Set[str]] = {}

    for inc in active_incidents:
        # Report responders
        norm_report = set(inc.get_normalized_responders())
        incident_report_map[inc.incident_number] = norm_report
        roster_set.update(norm_report)

        # Re-parse CAD notes if available to ensure live sync with members
        if inc.cad_notes and cad_parser:
            tokens, radio_resp, unmapped = cad_parser.parse_cad_text(
                cad_text=inc.cad_notes,
                incident_number=inc.incident_number,
                incident_date=inc.incident_date,
            )
            # Replace (not merge) results from the scrape-time pass: that pass can run before
            # all member badges were learned, which would leave stale "unmapped" marks behind.
            inc.radio_markups_found = list(dict.fromkeys(tokens))
            inc.radio_responders = list(dict.fromkeys(radio_resp))
            inc.unmapped_radio_marks = list({u.token: u for u in unmapped}.values())
            inc.radio_units = [u for u in (extract_unit_from_token(t) for t in tokens) if u]

        # Radio responders
        norm_radio = {normalize_personnel_name(r) or r for r in inc.radio_responders if r}
        incident_radio_map[inc.incident_number] = norm_radio
        roster_set.update(norm_radio)

        # Audit unmapped marks
        for mark in inc.unmapped_radio_marks:
            all_unmapped_cad_marks.append(mark)
            unmapped_cad_frequency[mark.token] += 1

    sorted_roster = sorted(list(roster_set))
    total_incidents = len(active_incidents)

    _log("Compiling multi-source attendance matrices across active incidents...")
    # 3. Build multi-source attendance matrices (Report, Radio, Combined)
    report_attendance_matrix: Dict[str, Dict[str, bool]] = {}
    radio_attendance_matrix: Dict[str, Dict[str, bool]] = {}
    combined_attendance_matrix: Dict[str, Dict[str, bool]] = {}
    member_calls_counter: Counter = Counter()

    for inc in active_incidents:
        report_responders = incident_report_map[inc.incident_number]
        radio_responders = incident_radio_map[inc.incident_number]

        rep_row: Dict[str, bool] = {}
        rad_row: Dict[str, bool] = {}
        comb_row: Dict[str, bool] = {}

        for member in sorted_roster:
            on_report = member in report_responders
            on_radio = member in radio_responders
            on_comb = on_report or on_radio

            rep_row[member] = on_report
            rad_row[member] = on_radio
            comb_row[member] = on_comb

            if on_comb:
                member_calls_counter[member] += 1

        report_attendance_matrix[inc.incident_number] = rep_row
        radio_attendance_matrix[inc.incident_number] = rad_row
        combined_attendance_matrix[inc.incident_number] = comb_row

    _log("Calculating individual member response counts and percentages...")
    # 4. Build AttendanceSummary per member (including 0-call members)
    personnel_summaries: Dict[str, AttendanceSummary] = {}
    for member in sorted_roster:
        calls = member_calls_counter[member]
        pct = (calls / total_incidents * 100.0) if total_incidents > 0 else 0.0
        formatted = f"{calls}/{total_incidents} ({pct:.1f}%)"
        personnel_summaries[member] = AttendanceSummary(
            person_name=member,
            calls_made=calls,
            total_incidents=total_incidents,
            percentage=pct,
            formatted_ratio=formatted,
        )

    _log("Aggregating incident type breakdown and apparatus dispatch frequencies...")
    # 4. Build IncidentTypeSummary breakdown
    type_counter: Counter = Counter()
    for inc in active_incidents:
        inc_type = inc.incident_type.strip() if inc.incident_type else "Uncategorized"
        type_counter[inc_type] += 1

    sorted_types = sorted(type_counter.items(), key=lambda x: (-x[1], x[0]))
    type_summaries: List[IncidentTypeSummary] = []
    for inc_type, count in sorted_types:
        pct = (count / total_incidents * 100.0) if total_incidents > 0 else 0.0
        formatted = f"{inc_type}: {count}/{total_incidents} ({pct:.1f}%)"
        type_summaries.append(
            IncidentTypeSummary(
                incident_type=inc_type,
                count=count,
                percentage=pct,
                formatted_summary=formatted,
            )
        )

    # 5. Build ApparatusSummary breakdown
    apparatus_counter: Counter = Counter()
    for inc in active_incidents:
        # Collect unique apparatus involved in this call
        inc_apparatus: Set[str] = set()
        for app in inc.apparatus:
            app_clean = normalize_apparatus_name(app)
            if app_clean:
                inc_apparatus.add(app_clean)
        # Also check person_apparatus
        for app in inc.person_apparatus.values():
            app_clean = normalize_apparatus_name(app)
            if app_clean:
                inc_apparatus.add(app_clean)

        for app_name in inc_apparatus:
            apparatus_counter[app_name] += 1

    sorted_apparatus = sorted(apparatus_counter.items(), key=lambda x: (-x[1], x[0]))
    apparatus_summaries: List[ApparatusSummary] = []
    for app_name, count in sorted_apparatus:
        pct = (count / total_incidents * 100.0) if total_incidents > 0 else 0.0
        formatted = f"{app_name}: {count}/{total_incidents} ({pct:.1f}%)"
        apparatus_summaries.append(
            ApparatusSummary(
                apparatus_name=app_name,
                count=count,
                percentage=pct,
                formatted_summary=formatted,
            )
        )

    _log("Segregating inactive and draft calls for administrative audit...")
    _log(f"Identified {len(sorted_roster)} responders across {total_incidents} active calls ({len(inactive_incidents)} inactive/drafts).")
    _log("Roster and attendance analysis complete.")

    # 6. Build Unit-oriented Roster & Attendance Matrix for Sheet 1 ("Call Percentage")
    _log("Compiling unit number roster (1510 - 1564) and unit-level attendance...")
    # Base units: always include 1510 - 1564
    ALL_DEFAULT_UNITS = [str(u) for u in range(1510, 1565)]

    # Resolve members source for unit mapping: use members_db or load_members()
    ref_members = members_db if members_db is not None else load_members()

    unit_to_name: Dict[str, str] = {}
    name_to_unit: Dict[str, str] = {}

    if ref_members:
        for m in ref_members:
            disp_name = format_display_name(m.name)
            norm_name = normalize_personnel_name(m.name)
            u_cand = extract_unit_from_token(m.primary_id) or (m.primary_id.strip() if m.primary_id else None)
            if u_cand:
                unit_to_name[u_cand] = disp_name
                name_to_unit[norm_name] = u_cand
                name_to_unit[m.name] = u_cand
                name_to_unit[disp_name] = u_cand
                for alias in m.aliases:
                    name_to_unit[alias.upper()] = u_cand

    # Also harvest unit badges directly from incident responders
    for inc in active_incidents:
        for resp in inc.responders:
            norm, badge = extract_name_and_badge(resp)
            disp = format_display_name(norm)
            if badge:
                u = extract_unit_from_token(badge) or badge.strip()
                if u:
                    unit_to_name[u] = disp
                    name_to_unit[norm] = u
                    name_to_unit[disp] = u

    # Combine into sorted unit roster: always includes 1510-1564, plus any extra primary unit numbers
    unit_set = set(ALL_DEFAULT_UNITS)
    for u in unit_to_name.keys():
        if u and (1510 <= int(u) <= 1564 if u.isdigit() else False):
            unit_set.add(u)

    sorted_units = sorted(
        list(unit_set),
        key=lambda x: (int(x) if x.isdigit() else 9999, x)
    )

    # Ensure all units have a name entry (blank if unmapped)
    for u in sorted_units:
        if u not in unit_to_name:
            unit_to_name[u] = ""

    # Build unit attendance matrix: incident_number -> {unit_number: bool}
    unit_attendance_matrix: Dict[str, Dict[str, bool]] = {}
    for inc in active_incidents:
        attended_units: Set[str] = set()

        # Responders on report
        for resp in inc.responders:
            norm, badge = extract_name_and_badge(resp)
            u = (extract_unit_from_token(badge) if badge else None) or name_to_unit.get(norm) or name_to_unit.get(format_display_name(norm))
            if u:
                attended_units.add(u)

        # Responders from radio
        for r in inc.radio_responders:
            norm = normalize_personnel_name(r)
            u = name_to_unit.get(norm) or name_to_unit.get(format_display_name(norm))
            if u:
                attended_units.add(u)

        # Explicit unit numbers in CAD notes
        for token in inc.radio_markups_found:
            u = extract_unit_from_token(token)
            if u:
                attended_units.add(u)

        for u in getattr(inc, "radio_units", []):
            if u:
                attended_units.add(u)

        unit_attendance_matrix[inc.incident_number] = {
            u: (u in attended_units) for u in sorted_units
        }

    # 7. CAD entry legend: resolves each distinct entry the same way the matrix above does
    legend_counts: Counter = Counter()
    legend_raw: Dict[str, str] = {}
    for inc in active_incidents:
        entries = {" ".join(t.upper().split()): t for t in inc.radio_markups_found}
        legend_counts.update(entries.keys())
        for entry, raw in entries.items():
            legend_raw.setdefault(entry, raw)

    on_sheet = set(sorted_units)
    cad_legend: List[CADLegendEntry] = []
    for entry, seen in legend_counts.items():
        raw = legend_raw[entry]
        member = cad_parser.match_token_to_member(raw) if cad_parser else None
        member_unit = None
        if member and member.active and member.name:
            norm = normalize_personnel_name(member.name)
            member_unit = name_to_unit.get(norm) or name_to_unit.get(format_display_name(norm))
        token_unit = extract_unit_from_token(raw)

        unit = next((u for u in (member_unit, token_unit) if u in on_sheet), None)
        if unit:
            status = "Marks attendance"
        elif member_unit or token_unit:
            unit = member_unit or token_unit
            status = "Unit not on sheet"
        else:
            status = "No match"
        cad_legend.append(
            CADLegendEntry(
                cad_entry=entry,
                unit_number=unit or "",
                member_name=unit_to_name.get(unit, "") if unit else "",
                status=status,
                times_seen=seen,
            )
        )
    cad_legend.sort(key=lambda e: (e.status == "No match", int(e.unit_number) if e.unit_number.isdigit() else 9999, e.cad_entry))

    return ReportDataset(
        start_date=start_date,
        end_date=end_date,
        total_incidents=total_incidents,
        roster=sorted_roster,
        incidents=active_incidents,
        inactive_incidents=inactive_incidents,
        attendance_matrix=combined_attendance_matrix,
        report_attendance_matrix=report_attendance_matrix,
        radio_attendance_matrix=radio_attendance_matrix,
        combined_attendance_matrix=combined_attendance_matrix,
        all_unmapped_cad_marks=all_unmapped_cad_marks,
        unmapped_cad_frequency=dict(unmapped_cad_frequency),
        cad_legend=cad_legend,
        personnel_summaries=personnel_summaries,
        type_summaries=type_summaries,
        apparatus_summaries=apparatus_summaries,
        unit_roster=sorted_units,
        unit_to_name=unit_to_name,
        unit_attendance_matrix=unit_attendance_matrix,
    )
