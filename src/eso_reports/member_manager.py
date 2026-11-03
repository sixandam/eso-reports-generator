"""
Member management module for ESO Suite Reports.
Handles loading, saving, importing, and exporting department personnel,
radio call signs, and dispatcher aliases from members.json.
"""

from __future__ import annotations
import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .config import MEMBERS_FILE, APP_CONFIG_DIR
from .models import Member, normalize_personnel_name

logger = logging.getLogger(__name__)

# Default department profile (Lyn-Dan Heights Fire Dept / Company 15 presets)
DEFAULT_SEEDED_MEMBERS: List[Dict] = [
    {
        "name": "Wellons, Charles",
        "primary_id": "1534",
        "aliases": ["CHF 15", "CF15", "CHIEF 15", "1501", "15-01", "1534", "15-34"],
        "active": True,
    },
    {
        "name": "Glass, Lucas",
        "primary_id": "1545",
        "aliases": ["1545", "15-45"],
        "active": True,
    },
    {
        "name": "Glass, Ryne",
        "primary_id": "1530",
        "aliases": ["1530", "15-30"],
        "active": True,
    },
]


def get_default_members_file() -> Path:
    """Returns resolved path to members.json, ensuring parent directory exists."""
    try:
        APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return MEMBERS_FILE


def load_members(file_path: Optional[Path] = None) -> List[Member]:
    """
    Loads department members from members.json.
    If the file does not exist, seeds it with default department presets and saves it.
    """
    target = file_path or get_default_members_file()
    if not target.exists():
        members = [Member(**m) for m in DEFAULT_SEEDED_MEMBERS]
        try:
            save_members(members, target)
        except Exception as e:
            logger.warning(f"Could not persist default members to {target}: {e}")
        return members

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(data, list):
            members = []
            for item in data:
                if isinstance(item, dict):
                    # Ensure name is normalized
                    raw_name = item.get("name", "")
                    norm_name = normalize_personnel_name(raw_name) or raw_name
                    item["name"] = norm_name
                    members.append(Member(**item))
            return members
    except Exception as e:
        logger.error(f"Error loading members from {target}: {e}")

    return [Member(**m) for m in DEFAULT_SEEDED_MEMBERS]


def save_members(members: List[Member], file_path: Optional[Path] = None) -> None:
    """Saves department members to members.json formatted with indent for clean editing."""
    target = file_path or get_default_members_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = [m.model_dump() for m in members]
    target.write_text(json.dumps(serialized, indent=2), encoding="utf-8")


def export_members_to_csv(members: List[Member], csv_path: Path) -> None:
    """Exports members to a CSV file."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Primary ID", "Aliases", "Active"])
        for m in members:
            aliases_str = "; ".join(m.aliases)
            writer.writerow([m.name, m.primary_id, aliases_str, "Yes" if m.active else "No"])


def import_members_from_csv(csv_path: Path) -> List[Member]:
    """Imports members from a CSV file, merging or replacing entries."""
    imported: List[Member] = []
    with open(csv_path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name_raw = row.get("Name") or row.get("name") or ""
            norm_name = normalize_personnel_name(name_raw) or name_raw.strip()
            if not norm_name:
                continue

            primary_id = (row.get("Primary ID") or row.get("primary_id") or row.get("ID") or "").strip()
            aliases_raw = (row.get("Aliases") or row.get("aliases") or "").strip()
            # Split aliases by semicolon or comma
            aliases: List[str] = []
            if aliases_raw:
                delim = ";" if ";" in aliases_raw else ","
                aliases = [a.strip() for a in aliases_raw.split(delim) if a.strip()]

            active_val = (row.get("Active") or row.get("active") or "yes").strip().lower()
            is_active = active_val in ("yes", "true", "1", "y")

            # Always ensure primary_id is included in aliases if given
            if primary_id and primary_id not in aliases:
                aliases.insert(0, primary_id)

            imported.append(
                Member(
                    name=norm_name,
                    primary_id=primary_id,
                    aliases=aliases,
                    active=is_active,
                )
            )
    return imported


def get_active_roster_names(members: List[Member]) -> List[str]:
    """Returns sorted list of active member names for known_roster."""
    return sorted(list({m.name for m in members if m.active and m.name}))

