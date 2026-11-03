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
    normalize_personnel_name,
)
from .member_manager import load_members
from .cad_parser import CADParser


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
            inc.radio_markups_found = list(dict.fromkeys(inc.radio_markups_found + tokens))
            inc.radio_responders = list(dict.fromkeys(inc.radio_responders + radio_resp))
            existing_unmapped = {u.token for u in inc.unmapped_radio_marks}
            for u in unmapped:
                if u.token not in existing_unmapped:
                    inc.unmapped_radio_marks.append(u)
                    existing_unmapped.add(u.token)

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
        personnel_summaries=personnel_summaries,
        type_summaries=type_summaries,
        apparatus_summaries=apparatus_summaries,
    )
