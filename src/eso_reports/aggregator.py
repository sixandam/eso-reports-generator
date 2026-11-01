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
    normalize_personnel_name,
)


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
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> ReportDataset:
    """
    Transforms a list of incidents into structured report data.

    Calculates:
    - Roster list sorted alphabetically.
    - Attendance matrix indicating which personnel responded to each incident ('X' / '').
    - Attendance metrics per member: calls_made, total_incidents, percentage, formatted_ratio ("n/N (n%)").
    - Incident type distribution: count, percentage, formatted_summary ("<Type>: n/N (n%)").
    - Apparatus distribution: count, percentage, formatted_summary ("<Apparatus>: n/N (n%)").
    """
    def _log(msg: str):
        if log_callback:
            log_callback(msg)

    _log("Normalizing personnel names and building department roster...")
    # 0. Segregate active incidents from inactive/discarded placeholder records
    active_incidents = [inc for inc in incidents if (inc.status or "ACTIVE").upper() != "INACTIVE"]
    inactive_incidents = [inc for inc in incidents if (inc.status or "ACTIVE").upper() == "INACTIVE"]

    # 1. Collect and normalize all personnel in the roster
    roster_set: Set[str] = set()

    if known_roster:
        for name in known_roster:
            norm = normalize_personnel_name(name)
            if norm:
                roster_set.add(norm)

    # Add all responders from active incident records
    incident_responders_map: Dict[str, Set[str]] = {}
    for inc in active_incidents:
        norm_responders = set(inc.get_normalized_responders())
        incident_responders_map[inc.incident_number] = norm_responders
        roster_set.update(norm_responders)

    sorted_roster = sorted(list(roster_set))
    total_incidents = len(active_incidents)

    _log("Compiling member attendance matrix across all active incidents...")
    # 2. Build attendance matrix & calculate member call counts
    attendance_matrix: Dict[str, Dict[str, bool]] = {}
    member_calls_counter: Counter = Counter()

    for inc in active_incidents:
        responders = incident_responders_map[inc.incident_number]
        inc_matrix: Dict[str, bool] = {}
        for member in sorted_roster:
            responded = member in responders
            inc_matrix[member] = responded
            if responded:
                member_calls_counter[member] += 1
        attendance_matrix[inc.incident_number] = inc_matrix

    _log("Calculating individual member response counts and percentages...")
    # 3. Build AttendanceSummary per member
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
        attendance_matrix=attendance_matrix,
        personnel_summaries=personnel_summaries,
        type_summaries=type_summaries,
        apparatus_summaries=apparatus_summaries,
    )
