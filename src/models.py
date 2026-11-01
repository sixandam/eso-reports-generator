"""
Data models and schemas for ESO Suite incident reports.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


SUFFIX_MAP = {
    "jr": "Jr.",
    "jr.": "Jr.",
    "sr": "Sr.",
    "sr.": "Sr.",
    "ii": "II",
    "iii": "III",
    "iv": "IV",
    "v": "V",
    "vi": "VI",
}


def _format_name_token(token: str) -> str:
    """Formats a single first/middle name token, ensuring initials have periods."""
    t = token.strip()
    if not t:
        return ""
    if len(t) == 1 and t.isalpha():
        return f"{t.upper()}."
    if len(t) == 2 and t[1] == "." and t[0].isalpha():
        return t.upper()
    return t.title()


def normalize_personnel_name(raw_name: str) -> str:
    """
    Standardize personnel names to 'Last, First' format with proper suffix handling.
    Strips badge suffixes (e.g., ' | 1534'), handles extra whitespace, initials,
    generational Roman numerals (II, III, IV), and suffix tokens (Jr., Sr.).
    - 'Wellons, Charles | 1534' -> 'Wellons, Charles'
    - 'Garber, James Steven, JR | 1539' -> 'Garber, James Steven, Jr.'
    - 'Smith, John, III' -> 'Smith, John, III'
    - 'John Smith, Jr.' -> 'Smith, John, Jr.'
    - 'Adams, John' -> 'Adams, John'
    - 'John Adams' -> 'Adams, John'
    - 'ADAMS, J.' -> 'Adams, J.'
    - 'Adams, J' -> 'Adams, J.'
    """
    clean = " ".join(raw_name.strip().split())
    if not clean:
        return ""

    # Strip badge number / ID suffix like " | 1534"
    if "|" in clean:
        clean = clean.split("|")[0].strip()

    # Normalize multiple commas and extract suffix
    comma_parts = [p.strip() for p in clean.split(",") if p.strip()]

    # Case 1: Comma-separated parts
    if len(comma_parts) >= 2:
        # Check if the last part is a generational suffix (Jr, Sr, III, etc.)
        last_part_lower = comma_parts[-1].lower()
        suffix = ""
        if last_part_lower in SUFFIX_MAP:
            suffix = f", {SUFFIX_MAP[last_part_lower]}"
            comma_parts = comma_parts[:-1]

        if len(comma_parts) == 1:
            # e.g. "John Smith, Jr." where "Jr." was stripped leaving "John Smith"
            tokens = comma_parts[0].split()
            if len(tokens) >= 2:
                last = tokens[-1].title()
                first = " ".join(_format_name_token(t) for t in tokens[:-1])
                return f"{last}, {first}{suffix}"
            return f"{comma_parts[0].title()}{suffix}"

        # Standard "Last, First [Middle]"
        last = comma_parts[0].title()
        rest_tokens = comma_parts[1].split()

        # Check if suffix was included in the first name without comma, e.g. "John Jr."
        if rest_tokens and rest_tokens[-1].lower() in SUFFIX_MAP and not suffix:
            suffix = f", {SUFFIX_MAP[rest_tokens[-1].lower()]}"
            rest_tokens = rest_tokens[:-1]

        first_formatted = " ".join(_format_name_token(t) for t in rest_tokens)
        return f"{last}, {first_formatted}{suffix}" if first_formatted else f"{last}{suffix}"

    # Case 2: Space-separated format without commas, e.g. "First Last", "First Last Jr"
    tokens = clean.split()
    if not tokens:
        return ""

    suffix = ""
    if tokens[-1].lower() in SUFFIX_MAP and len(tokens) > 2:
        suffix = f", {SUFFIX_MAP[tokens[-1].lower()]}"
        tokens = tokens[:-1]

    if len(tokens) == 1:
        return tokens[0].title()
    elif len(tokens) == 2:
        first, last = _format_name_token(tokens[0]), tokens[1].title()
        return f"{last}, {first}{suffix}"
    else:
        last = tokens[-1].title()
        first = " ".join(_format_name_token(t) for t in tokens[:-1])
        return f"{last}, {first}{suffix}"


class Incident(BaseModel):
    """Represents a single fire/EMS incident record."""
    model_config = ConfigDict(extra="ignore")

    incident_number: str = Field(description="Unique department incident identifier (e.g., '24-00142')")
    incident_type: str = Field(description="Incident classification code and description (e.g., '111 - Building fire')")
    incident_date: Optional[str] = Field(default=None, description="Date/time string of the incident")
    record_id: Optional[str] = Field(default=None, description="Internal ESO record ID (e.g., '10852664')")
    status: Optional[str] = Field(default="ACTIVE", description="Record status (e.g. 'ACTIVE', 'IN REVIEW', 'DRAFT', 'INACTIVE')")
    responders: List[str] = Field(default_factory=list, description="List of personnel names who responded to this call")
    apparatus: List[str] = Field(default_factory=list, description="List of apparatus/resources that made the call (e.g., 'Engine 15', 'POV')")
    person_apparatus: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of normalized personnel name to apparatus/resource (e.g. {'Adams, J.': 'Engine 15'})"
    )
    details_fetched: bool = Field(default=False, description="Whether full incident record details have been harvested via API")
    raw_data: Optional[Dict[str, Any]] = Field(default=None, description="Optional raw backend payload")

    def get_normalized_responders(self) -> List[str]:
        """Return unique, normalized list of responder names."""
        unique_normalized = {
            normalize_personnel_name(name)
            for name in self.responders
            if name and normalize_personnel_name(name)
        }
        return sorted(list(unique_normalized))


class AttendanceSummary(BaseModel):
    """Summary metrics for a single personnel member."""
    model_config = ConfigDict(extra="ignore")

    person_name: str
    calls_made: int
    total_incidents: int
    percentage: float
    formatted_ratio: str  # e.g. "42/100 (42.0%)"


class IncidentTypeSummary(BaseModel):
    """Summary metrics for an incident type category."""
    model_config = ConfigDict(extra="ignore")

    incident_type: str
    count: int
    percentage: float
    formatted_summary: str  # e.g. "111 - Building fire: 14/50 (28.0%)"


class ApparatusSummary(BaseModel):
    """Summary metrics for an apparatus/resource."""
    model_config = ConfigDict(extra="ignore")

    apparatus_name: str
    count: int
    percentage: float
    formatted_summary: str  # e.g. "Engine 15: 18/50 (36.0%)"


class ReportDataset(BaseModel):
    """Full dataset ready for export to Excel."""
    model_config = ConfigDict(extra="ignore")

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_incidents: int
    roster: List[str]
    incidents: List[Incident]
    inactive_incidents: List[Incident] = Field(
        default_factory=list,
        description="List of inactive or discarded placeholder records segregated to Sheet 2"
    )
    attendance_matrix: Dict[str, Dict[str, bool]] = Field(
        description="Map of incident_number -> {person_name: responded_bool}"
    )
    personnel_summaries: Dict[str, AttendanceSummary]
    type_summaries: List[IncidentTypeSummary]
    apparatus_summaries: List[ApparatusSummary] = Field(
        default_factory=list,
        description="Apparatus response frequencies and percentages"
    )
