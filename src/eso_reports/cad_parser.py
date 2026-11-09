"""
CAD notes parsing and dispatcher notation typo-correction engine.
Extracts radio call signs, handles variations, applies typo corrections,
and maps tokens to department members or records unmapped audit marks.
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Set, Tuple

from .models import Member, UnmappedCADMark

# Non-callsign keywords to prevent false extraction
IGNORE_TOKENS = {
    "POV", "STATION", "STN", "SCENE", "EN ROUTE", "ENROUTE",
    "ON SCENE", "IN SERVICE", "AVAIL", "AVAILABLE", "CLEAR",
    "CANCELLED", "DISPATCH", "DISP", "RADIO", "TAC", "OPS",
    "PAGE", "PAGED", "TONE", "TONES", "ALERT", "ALERTS",
}

# The company number on its own ("Company 15", "Station 15") is never a member call sign.
# Members are only identified by full forms such as 1515, 15-15 or 15 15.
COMPANY_NUMBER = "15"


def is_reserved_alias(alias: str) -> bool:
    """True for aliases that must never identify a member (the bare company number)."""
    return " ".join(str(alias or "").split()) == COMPANY_NUMBER


# Apparatus / company / station prefixes: "ENG15", "TRUCK 15", "CO15", "CMD15" name a vehicle
# or the company, not a member, so they are neither mapped nor flagged as unknown call signs.
APPARATUS_PREFIXES = {
    "CO", "COMPANY", "STA", "STN", "STATION", "ENG", "ENGINE", "E", "TRK", "TRUCK", "LADDER", "LAD",
    "TWR", "TOWER", "CMD", "COMMAND", "PMPR", "PUMPER", "RES", "RESCUE", "SQ", "SQUAD", "MED", "MEDIC",
    "AMB", "BRUSH", "BR", "TNK", "TANKER", "TENDER", "UTIL", "UTILITY", "UNIT", "AIR", "BOAT",
}


# Common dispatcher command variations mapped to standard
COMMAND_CORRECTIONS = {
    "CHEIF": "CHIEF",
    "CHFE": "CHIEF",
    "CHEIF15": "CHIEF 15",
    "CHFE15": "CHIEF 15",
    "CEF": "CF",
    "CEF15": "CF 15",
}


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculates Damerau-Levenshtein edit distance between two strings, including adjacent transpositions."""
    s1, s2 = s1.upper(), s2.upper()
    d = {}
    len1, len2 = len(s1), len(s2)
    for i in range(-1, len1 + 1):
        d[(i, -1)] = i + 1
    for j in range(-1, len2 + 1):
        d[(-1, j)] = j + 1

    for i in range(len1):
        for j in range(len2):
            cost = 0 if s1[i] == s2[j] else 1
            d[(i, j)] = min(
                d[(i - 1, j)] + 1,          # deletion
                d[(i, j - 1)] + 1,          # insertion
                d[(i - 1, j - 1)] + cost,   # substitution
            )
            if i > 0 and j > 0 and s1[i] == s2[j - 1] and s1[i - 1] == s2[j]:
                d[(i, j)] = min(d[(i, j)], d[(i - 2, j - 2)] + 1)  # transposition

    return d[(len1 - 1, len2 - 1)]


def clean_cad_snippet(line: str) -> str:
    """Cleans a single CAD line or remark for display in audit tables."""
    return " ".join(line.strip().split())


def normalize_numeric_token(token: str) -> str:
    """
    Normalizes numeric radio call signs by replacing common typo confusions:
    - Letter 'O' or 'o' -> '0'
    - Letter 'I', 'l', or 'i' -> '1'
    - Letter 'S' or 's' -> '5' (when following '1' in 15xx context)
    - Strips leading '#' or 'M'
    - Normalizes hyphens ('15 - 16' -> '15-16')
    """
    clean = token.strip()
    if clean.startswith("#") or (clean.startswith(("M", "m")) and len(clean) > 2 and clean[1:].strip(" -").isalnum()):
        clean = clean[1:].strip()

    # Normalize spacing around hyphens
    clean = re.sub(r"\s*-\s*", "-", clean)

    # Substitution for 4-digit or hyphenated badges
    substitutions = {"O": "0", "o": "0", "I": "1", "l": "1", "i": "1"}
    chars = list(clean)
    for idx, c in enumerate(chars):
        if c in substitutions:
            # Only substitute if surrounding or subsequent characters are digits
            chars[idx] = substitutions[c]

    # Handle 'S' / 's' for '5' if preceded by '1' in Company 15 pattern (e.g. 1S16 -> 1516)
    for idx in range(len(chars)):
        if chars[idx] in ("S", "s") and idx > 0 and chars[idx - 1] == "1":
            chars[idx] = "5"

    return "".join(chars)


def normalize_command_token(token: str) -> str:
    """Normalizes officer command notations (e.g. 'CHF  15' -> 'CHF 15', 'CHEIF 15' -> 'CHIEF 15')."""
    clean = " ".join(token.strip().split())
    clean_upper = clean.upper()

    # Direct dictionary corrections
    for typo, correction in COMMAND_CORRECTIONS.items():
        if clean_upper == typo or clean_upper.startswith(typo + " "):
            clean_upper = clean_upper.replace(typo, correction)

    # Ensure single space between command and unit number (e.g. 'CHF15' -> 'CHF 15')
    match = re.match(r"^([A-Z]+)(\d+)$", clean_upper)
    if match:
        clean_upper = f"{match.group(1)} {match.group(2)}"

    return clean_upper


def extract_unit_from_token(token: str) -> Optional[str]:
    """
    Extracts standard 4-digit unit number from a token (e.g. 1510-1564, 15-34, #1534, 34).
    Returns normalized 4-digit string e.g. '1534' or None.
    """
    if not token:
        return None
    clean = normalize_numeric_token(token).replace("-", "").replace(" ", "").strip()
    if clean.isdigit():
        val = int(clean)
        if len(clean) == 4 and 1500 <= val <= 1599:
            return clean
        elif len(clean) in (1, 2) and 10 <= val <= 64 and clean != COMPANY_NUMBER:
            return f"15{val:02d}"
    return None


class CADParser:
    """
    Parser for CAD narrative text to detect radio markups and match against member aliases.
    """

    def __init__(self, members: List[Member]):
        self.members = members
        self._build_member_indices()

    def _build_member_indices(self):
        """Indexes active and inactive members by primary ID and aliases."""
        self.exact_alias_map: Dict[str, Member] = {}
        self.normalized_alias_map: Dict[str, Member] = {}
        self.all_configured_tokens: Set[str] = set()

        for m in self.members:
            # Collect all variations for this member
            candidates = set()
            if m.primary_id:
                candidates.add(m.primary_id)
            for a in m.aliases:
                candidates.add(a)

            for cand in candidates:
                cand_clean = cand.strip()
                if not cand_clean or is_reserved_alias(cand_clean):
                    continue
                cand_upper = cand_clean.upper()
                self.exact_alias_map[cand_upper] = m
                self.all_configured_tokens.add(cand_upper)

                # Normalized version
                norm_cand = self._normalize_any(cand_clean)
                self.normalized_alias_map[norm_cand] = m
                # Also store hyphen-stripped version if applicable
                no_hyphen = norm_cand.replace("-", "")
                if no_hyphen != norm_cand:
                    self.normalized_alias_map[no_hyphen] = m

    def _normalize_any(self, token: str) -> str:
        """Applies numeric and command normalization."""
        token_upper = " ".join(token.strip().split()).upper()
        if any(c.isalpha() for c in token_upper) and any(c.isdigit() for c in token_upper):
            # Could be CHF 15 or 15O6
            if re.match(r"^[A-Z]+\s*\d+$", token_upper) or any(cmd in token_upper for cmd in ("CHF", "CF", "CHIEF", "CAPT", "LT")):
                return normalize_command_token(token_upper)
        return normalize_numeric_token(token_upper)

    def match_token_to_member(self, token: str) -> Optional[Member]:
        """
        Attempts to match a candidate radio token using the 4-tier hierarchy:
        Tier 1: Exact Alias Match (case-insensitive)
        Tier 2: Normalized Match (OCR/typo substitution, hyphen stripping)
        Tier 3: Fuzzy Match (Levenshtein distance <= 1 on command terms)
        Returns matched Member or None.
        """
        raw_upper = " ".join(token.strip().split()).upper()
        if not raw_upper or raw_upper in IGNORE_TOKENS or is_reserved_alias(raw_upper):
            return None

        # Tier 1: Exact alias match
        if raw_upper in self.exact_alias_map:
            return self.exact_alias_map[raw_upper]

        # Tier 2: Normalized match
        norm = self._normalize_any(raw_upper)
        if norm in self.normalized_alias_map:
            return self.normalized_alias_map[norm]

        no_hyphen = norm.replace("-", "").replace(" ", "")
        if no_hyphen in self.normalized_alias_map:
            return self.normalized_alias_map[no_hyphen]

        # Tier 3: Fuzzy match (restricted strictly to command titles of len >= 4 followed by same number)
        # e.g. "CHEIF 15" -> "CHIEF 15" (does NOT match 3-letter typos like "CHG 15" which are flagged as questionable)
        cmd_match = re.match(r"^([A-Z]+)\s*(\d+)$", norm)
        if cmd_match:
            cmd_part, num_part = cmd_match.group(1), cmd_match.group(2)
            if len(cmd_part) >= 4:
                for target_alias, target_member in self.exact_alias_map.items():
                    target_cmd_match = re.match(r"^([A-Z]+)\s*(\d+)$", target_alias)
                    if target_cmd_match:
                        t_cmd, t_num = target_cmd_match.group(1), target_cmd_match.group(2)
                        if len(t_cmd) >= 4 and num_part == t_num and levenshtein_distance(cmd_part, t_cmd) <= 1:
                            return target_member

        return None

    def extract_candidate_tokens(self, text: str) -> List[Tuple[str, str]]:
        """
        Scans CAD text line by line and extracts candidate radio tokens along with the snippet line.
        Returns list of tuples: (candidate_token, raw_line).
        """
        if not text:
            return []

        results: List[Tuple[str, str]] = []
        # ESO delivers CAD notes as one line: "11/6/2026 17:19:49 - 1535 ENRT; 11/6/2026 17:20:11 - 1503 ENRT"
        lines = [entry for line in text.splitlines() for entry in re.split(r";\s*(?=\d{1,2}/\d{1,2}/\d{4}\s)", line)]

        # Regex patterns for CAD markups:
        # 1. Officer / call sign patterns: CHF 15, CHG15, CF15, CHIEF 15, C-15, CAPT 15, LT 15, etc.
        pattern_officer = re.compile(
            r"\b[A-Z]{2,6}\s*[-#]?\s*(?:15|150[1-9]|15[0-9]{2})\b",
            re.IGNORECASE,
        )

        # 2. Badge / member number patterns:
        # Matches 1516, 15-16, 15 16, #1516, M1516, 15O6, 1S16, l516
        pattern_numeric = re.compile(
            r"(?:(?<=\s)|(?<=^)|(?<=[#,;&]))(?:#|M|m)?(?:[1lI][5sS][0-9oOIlSs]{2}|[1lI][5sS]\s*-\s*[0-9oOIlSs]{2}|15 [0-9]{2})(?=(?:[\s,.;&]|$))",
            re.IGNORECASE,
        )

        # 3. Explicit check for configured aliases that might not match above regex
        custom_patterns = []
        for alias in self.all_configured_tokens:
            # Short numeric aliases ("10", "34") also appear as ordinary numbers in CAD text
            # ("10/4", dates, addresses, "Station 14"), so they are not searched for as call signs.
            if re.fullmatch(r"\d{1,2}", alias):
                continue
            if not pattern_officer.match(alias) and not pattern_numeric.match(alias):
                custom_patterns.append(re.escape(alias))

        pattern_custom = re.compile(r"\b(" + "|".join(custom_patterns) + r")\b", re.IGNORECASE) if custom_patterns else None

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Strip timestamp prefixes like "[20:26:01]" or "10/17/2026 20:25:30 -"
            clean_line = re.sub(r"^\[.*?\]\s*", "", line)
            clean_line = re.sub(r"^\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*[-:]?\s*", "", clean_line)

            # Match officer tokens
            for m in pattern_officer.finditer(clean_line):
                token = m.group(0).strip()
                prefix = re.match(r"[A-Za-z]+", token).group(0).upper()
                if token.upper() not in IGNORE_TOKENS and prefix not in APPARATUS_PREFIXES and prefix not in IGNORE_TOKENS:
                    results.append((token, line))

            # Match numeric tokens
            for m in pattern_numeric.finditer(clean_line):
                token = m.group(0).strip(" ,;/&")
                if token.upper() not in IGNORE_TOKENS:
                    results.append((token, line))

            # Match custom aliases if defined
            if pattern_custom:
                for m in pattern_custom.finditer(clean_line):
                    token = m.group(0).strip()
                    if token.upper() not in IGNORE_TOKENS:
                        results.append((token, line))

        return results

    def parse_cad_text(
        self,
        cad_text: str,
        incident_number: str = "",
        incident_date: Optional[str] = None,
    ) -> Tuple[List[str], List[str], List[UnmappedCADMark]]:
        """
        Parses CAD narrative text, identifies radio responders, and captures unmapped marks.
        
        Returns:
            Tuple of:
            - tokens_found: List of unique raw radio tokens found
            - radio_responders: List of normalized member names mapped to active members
            - unmapped_marks: List of UnmappedCADMark records for audit log
        """
        candidates = self.extract_candidate_tokens(cad_text)
        tokens_found: List[str] = []
        radio_responders: List[str] = []
        unmapped_marks: List[UnmappedCADMark] = []

        seen_tokens: Set[str] = set()
        seen_responders: Set[str] = set()
        seen_unmapped: Set[str] = set()

        for raw_token, snippet in candidates:
            token_upper = raw_token.upper().strip()
            if not token_upper or token_upper in IGNORE_TOKENS:
                continue

            if token_upper not in seen_tokens:
                seen_tokens.add(token_upper)
                tokens_found.append(raw_token)

            member = self.match_token_to_member(raw_token)
            if member:
                if member.active and member.name:
                    if member.name not in seen_responders:
                        seen_responders.add(member.name)
                        radio_responders.append(member.name)
            else:
                # Tier 4: Unmapped CAD Mark
                norm_tok = self._normalize_any(raw_token)
                unmapped_key = f"{norm_tok}:{incident_number}"
                if unmapped_key not in seen_unmapped:
                    seen_unmapped.add(unmapped_key)
                    unmapped_marks.append(
                        UnmappedCADMark(
                            token=norm_tok,
                            incident_number=incident_number,
                            incident_date=incident_date,
                            snippet=clean_cad_snippet(snippet),
                            reason=f"No active member associated with radio ID {norm_tok}",
                        )
                    )

        return tokens_found, sorted(radio_responders), unmapped_marks
