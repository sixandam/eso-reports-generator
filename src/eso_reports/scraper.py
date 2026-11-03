"""
Scraping and extraction engine for ESO Suite Fire Incidents RMS.
Extracts search records and drills down into:
  Incident Report > Resources > Personnel
to harvest responding personnel and their responding apparatus (Engine 15, POV, Station Standby, etc.).

Optimized with direct API request harvesting (/api/incident/{record_id}) for 30x faster extraction,
O(1) incident indexing, and persistent HTTP connection pooling.
"""

from __future__ import annotations
import http.client
import json
import logging
import re
import threading
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from playwright.sync_api import BrowserContext, Page, Response
from rich.console import Console

from .config import ESO_SEARCH_URL
from .models import Incident, normalize_personnel_name, Member, extract_name_and_badge
from .member_manager import load_members, auto_learn_member_badge
from .cad_parser import CADParser

logger = logging.getLogger(__name__)
console = Console()


def extract_cad_notes_from_payload(item: dict) -> Optional[str]:
    """
    Extracts raw CAD dispatch notes or narrative text from ESO API payload.
    Supports strings, lists of narrative dictionaries, and nested core/cad objects.
    """
    if not isinstance(item, dict):
        return None

    cad_candidates = [
        item.get("cadNotes"),
        item.get("cadComments"),
        item.get("cadRemarks"),
        item.get("cad"),
        item.get("dispatchInfo"),
        item.get("dispatchNotes"),
        item.get("narratives"),
        item.get("narrative"),
    ]
    core = item.get("core")
    if isinstance(core, dict):
        cad_candidates.extend([
            core.get("cadNotes"),
            core.get("cadComments"),
            core.get("cadRemarks"),
            core.get("cad"),
            core.get("comments"),
            core.get("narratives"),
            core.get("narrative"),
        ])

    lines: List[str] = []
    for cand in cad_candidates:
        if not cand:
            continue
        if isinstance(cand, str):
            clean = cand.strip()
            if clean and clean not in lines:
                lines.append(clean)
        elif isinstance(cand, list):
            for entry in cand:
                if isinstance(entry, str):
                    clean = entry.strip()
                    if clean and clean not in lines:
                        lines.append(clean)
                elif isinstance(entry, dict):
                    t = (
                        entry.get("text")
                        or entry.get("narrative")
                        or entry.get("comment")
                        or entry.get("remark")
                        or entry.get("content")
                        or entry.get("cadNotes")
                    )
                    if t and isinstance(t, str):
                        clean = t.strip()
                        if clean and clean not in lines:
                            lines.append(clean)
        elif isinstance(cand, dict):
            t = (
                cand.get("text")
                or cand.get("narrative")
                or cand.get("comment")
                or cand.get("remarks")
                or cand.get("notes")
            )
            if t and isinstance(t, str):
                clean = t.strip()
                if clean and clean not in lines:
                    lines.append(clean)

    if lines:
        return "\n".join(lines)
    return None


def format_date_for_eso(date_str: str) -> str:
    """
    Converts YYYY-MM-DD or other formats into ESO Suite's required MM/DD/YYYY format.
    e.g., '2026-09-01' -> '09/01/2026'.
    """
    clean = date_str.strip()
    try:
        if "-" in clean:
            dt = datetime.strptime(clean, "%Y-%m-%d")
            return dt.strftime("%m/%d/%Y")
        elif "/" in clean:
            parts = clean.split("/")
            if len(parts) == 3 and len(parts[0]) == 4:
                dt = datetime.strptime(clean, "%Y/%m/%d")
                return dt.strftime("%m/%d/%Y")
    except Exception:
        pass
    return clean


def is_uuid(value: str) -> bool:
    """Checks if a string is a GUID/UUID (e.g. 095140f5-fde5-ed11-a81c-000d3ae4ae10)."""
    if not value or len(value) < 30:
        return False
    return bool(re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", value.lower()))


class ESOScraper:
    """Extracts incident records, responding rosters, and apparatus from ESO Suite."""

    def __init__(
        self,
        context: BrowserContext,
        debug_log_path: Optional[Any] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        members: Optional[List[Member]] = None,
    ):
        self.context = context
        self.log_callback = log_callback
        self.members = members if members is not None else load_members()
        self.cad_parser = CADParser(self.members)
        self.intercepted_incidents: Dict[str, Incident] = {}
        # O(1) secondary lookup mapping internal ESO record_id to CAD incident_number
        self.record_id_to_inc_num: Dict[str, str] = {}
        self._lock = threading.Lock()

    def _log(self, message: str):
        """Outputs message to console and forwards to log_callback if registered."""
        console.print(message)
        if self.log_callback:
            # Strip rich markup for GUI display
            clean = re.sub(r"\[/?[a-zA-Z0-9_\s#=]+\]", "", message)
            self.log_callback(clean)

    def _setup_network_interception(self, page: Page):
        """
        Intercepts internal API responses delivering search records
        or full incident JSON payloads.
        """
        def handle_response(response: Response):
            url = response.url.lower()
            try:
                # Explicitly skip lookup/metadata endpoints that return agency personnel/units lists as UUIDs
                if any(skip in url for skip in ("/api/mdm-list", "/api/settings", "/api/valueset", "/api/entity", "/api/app-data", "/api/personnel")):
                    return

                # Target actual incident search and incident record endpoints
                if "application/json" in response.headers.get("content-type", ""):
                    if "/api/incident/" in url or "/api/incident-search" in url or "records/search" in url:
                        data = response.json()
                        self._process_api_payload(data, url)
            except Exception:
                pass

        page.on("response", handle_response)

    def _process_api_payload(self, data: Any, url: str):
        """Extract Incidents and Resources from backend JSON payloads."""
        if isinstance(data, dict):
            records = data.get("records") or data.get("data") or data.get("results") or data.get("items")
            if isinstance(records, list):
                for item in records:
                    self._parse_incident_dict(item)
            else:
                self._parse_incident_dict(data)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    self._parse_incident_dict(item)

    def _parse_incident_dict(self, item: dict):
        """
        Extracts incident fields from ESO API structure, eliminating duplicate entries
        and UUIDs from unrelated API calls.
        """
        # 1. Record ID (integer e.g. 10852664)
        raw_rec_id = (
            item.get("incidentId")
            or item.get("recordId")
            or item.get("incidentRecordId")
        )
        if not raw_rec_id and str(item.get("id", "")).isdigit():
            raw_rec_id = item.get("id")

        record_id = str(raw_rec_id) if raw_rec_id else None

        # 2. Extract Core data if present
        core = item.get("core") or {}
        incident_times = item.get("incidentTimes") or {}

        # CAD Incident Number (e.g. "CO15202600443")
        core_inc_num = (
            core.get("incidentNumber")
            or item.get("incidentNumber")
            or item.get("incident_number")
            or item.get("incidentNo")
        )

        # Primary Incident Type
        primary_type_obj = core.get("primaryIncidentTypeId")
        core_inc_type = None
        if isinstance(primary_type_obj, dict):
            core_inc_type = primary_type_obj.get("name")
        if not core_inc_type:
            core_inc_type = (
                item.get("incidentTypeDescription")
                or item.get("incidentType")
                or item.get("typeDescription")
                or core.get("initialDispatchCode")
            )

        # Incident Date
        core_date = (
            core.get("incidentOnsetDateTime")
            or incident_times.get("dispatchCallArrivalDateTime")
            or item.get("incidentDate")
            or item.get("date")
        )

        # Incident Status
        inc_status_id = item.get("incidentStatusTypeId") or core.get("incidentStatusTypeId")
        status_val = "INACTIVE" if (inc_status_id == 4 or str(item.get("status", "")).upper() == "INACTIVE") else "ACTIVE"

        # Skip items that are not incident records (e.g. metadata objects with UUID ids)
        if not core and not core_inc_num:
            if record_id and is_uuid(record_id):
                return
            if not record_id and not core_inc_num:
                return

        # Determine target incident number
        inc_num = str(core_inc_num).strip() if core_inc_num else None

        # Guard against UUID incident numbers
        if inc_num and is_uuid(inc_num):
            return

        responders: List[str] = []
        apparatus: List[str] = []
        person_apparatus: Dict[str, str] = {}

        # 3. Parse resources2.units (Live ESO RMS structure)
        resources2 = item.get("resources2") or {}
        units_list = resources2.get("units") or []
        for unit in units_list:
            if isinstance(unit, dict):
                unit_id_obj = unit.get("unitId")
                app_name = None
                if isinstance(unit_id_obj, dict):
                    app_name = unit_id_obj.get("name")
                if not app_name:
                    app_name = unit.get("name") or unit.get("apparatusName")

                if app_name:
                    app_clean = str(app_name).strip()
                    if app_clean not in apparatus:
                        apparatus.append(app_clean)

                # Unit personnel
                unit_crew = unit.get("personnel") or []
                for p in unit_crew:
                    if isinstance(p, dict):
                        agency_person = p.get("agencyPerson")
                        p_name = None
                        if isinstance(agency_person, dict):
                            p_name = agency_person.get("name")
                        if not p_name:
                            p_name = p.get("fullName") or p.get("name")
                        if p_name:
                            norm, badge = extract_name_and_badge(p_name)
                            if norm and norm not in responders:
                                responders.append(norm)
                            if app_name and norm:
                                person_apparatus[norm] = str(app_name).strip()
                            if norm and badge and hasattr(self, "members") and self.members is not None:
                                if auto_learn_member_badge(self.members, norm, badge):
                                    self.cad_parser = CADParser(self.members)

        # Check personnelNotOnUnit
        not_on_unit = resources2.get("personnelNotOnUnit") or []
        for p in not_on_unit:
            if isinstance(p, dict):
                agency_person = p.get("agencyPerson")
                p_name = agency_person.get("name") if isinstance(agency_person, dict) else p.get("name")
                if p_name:
                    norm, badge = extract_name_and_badge(p_name)
                    if norm and norm not in responders:
                        responders.append(norm)
                    if norm and badge and hasattr(self, "members") and self.members is not None:
                        if auto_learn_member_badge(self.members, norm, badge):
                            self.cad_parser = CADParser(self.members)

        # Fallback check for raw apparatus or personnel at top level
        raw_resources = item.get("resources") or item.get("apparatus")
        if isinstance(raw_resources, list):
            for res in raw_resources:
                if isinstance(res, dict):
                    a_name = res.get("apparatusName") or res.get("name")
                    if a_name and str(a_name).strip() not in apparatus:
                        apparatus.append(str(a_name).strip())

        raw_roster = item.get("personnel") or item.get("responders")
        if isinstance(raw_roster, list):
            for p in raw_roster:
                if isinstance(p, str):
                    norm, badge = extract_name_and_badge(p)
                    if norm and norm not in responders:
                        responders.append(norm)
                    if norm and badge and hasattr(self, "members") and self.members is not None:
                        if auto_learn_member_badge(self.members, norm, badge):
                            self.cad_parser = CADParser(self.members)

        has_details = bool(resources2 or raw_resources or raw_roster or core_inc_type)

        # 4. Extract CAD notes and parse radio markups
        cad_notes = extract_cad_notes_from_payload(item)
        radio_markups: List[str] = []
        radio_responders: List[str] = []
        unmapped_marks: List[Any] = []
        if cad_notes:
            radio_markups, radio_responders, unmapped_marks = self.cad_parser.parse_cad_text(
                cad_text=cad_notes,
                incident_number=inc_num or "",
                incident_date=core_date,
            )

        with self._lock:
            # Fast O(1) matching: check incident_number index or secondary record_id index
            target_incident = None
            if inc_num and inc_num in self.intercepted_incidents:
                target_incident = self.intercepted_incidents[inc_num]
            elif record_id and record_id in self.record_id_to_inc_num:
                indexed_num = self.record_id_to_inc_num[record_id]
                target_incident = self.intercepted_incidents.get(indexed_num)
                if not inc_num:
                    inc_num = indexed_num

            if not inc_num:
                if record_id and not is_uuid(record_id):
                    inc_num = record_id
                else:
                    return

            # Register secondary O(1) mapping
            if record_id and inc_num:
                self.record_id_to_inc_num[record_id] = inc_num

            # Merge with existing incident or insert new
            if target_incident:
                merged_responders = list(dict.fromkeys(target_incident.responders + responders))
                merged_apparatus = list(dict.fromkeys(target_incident.apparatus + apparatus))
                merged_pa = {**target_incident.person_apparatus, **person_apparatus}

                # Update incident type from authoritative core data
                final_type = target_incident.incident_type
                if core_inc_type:
                    final_type = core_inc_type
                elif not final_type or final_type in ("IN REVIEW", "DRAFT", "INACTIVE", "COMPLETED", "Unknown Incident Type") or "/" in final_type:
                    final_type = core_inc_type or "Unknown Incident Type"

                target_incident.incident_type = final_type
                target_incident.record_id = record_id or target_incident.record_id
                target_incident.incident_date = core_date or target_incident.incident_date
                if status_val == "INACTIVE":
                    target_incident.status = "INACTIVE"
                target_incident.responders = merged_responders
                target_incident.apparatus = merged_apparatus
                target_incident.person_apparatus = merged_pa
                if has_details:
                    target_incident.details_fetched = True
                if cad_notes:
                    if target_incident.cad_notes and cad_notes not in target_incident.cad_notes:
                        target_incident.cad_notes = target_incident.cad_notes + "\n" + cad_notes
                    elif not target_incident.cad_notes:
                        target_incident.cad_notes = cad_notes
                    target_incident.radio_markups_found = list(dict.fromkeys(target_incident.radio_markups_found + radio_markups))
                    target_incident.radio_responders = list(dict.fromkeys(target_incident.radio_responders + radio_responders))
                    existing_unmapped = {u.token for u in target_incident.unmapped_radio_marks}
                    for u in unmapped_marks:
                        if u.token not in existing_unmapped:
                            target_incident.unmapped_radio_marks.append(u)
                            existing_unmapped.add(u.token)
                # Protect PHI by discarding raw backend payload
                target_incident.raw_data = None
            else:
                new_inc = Incident(
                    incident_number=inc_num,
                    incident_type=core_inc_type or "Unknown Incident Type",
                    incident_date=core_date,
                    record_id=record_id,
                    status=status_val,
                    responders=responders,
                    apparatus=apparatus,
                    person_apparatus=person_apparatus,
                    details_fetched=has_details,
                    raw_data=None,
                    cad_notes=cad_notes,
                    radio_markups_found=radio_markups,
                    radio_responders=radio_responders,
                    unmapped_radio_marks=unmapped_marks,
                )
                self.intercepted_incidents[inc_num] = new_inc
                if record_id:
                    self.record_id_to_inc_num[record_id] = inc_num
                self._log(f"Incident {inc_num} found.")

    def search_and_extract(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Incident]:
        """
        1. Navigates to ESO Records Search.
        2. Applies date filters.
        3. Expands page size to 100 and iterates across pages to capture all incidents.
        4. Rapidly harvests resources & personnel via direct API requests with connection pooling.
        """
        page = self.context.new_page()
        try:
            return self._search_and_extract_internal(page, start_date, end_date)
        finally:
            try:
                page.close()
            except Exception:
                pass

    def _search_and_extract_internal(
        self,
        page: Page,
        start_date: str,
        end_date: str,
    ) -> List[Incident]:
        self._setup_network_interception(page)

        eso_start = format_date_for_eso(start_date)
        eso_end = format_date_for_eso(end_date)

        self._log(f"Connecting to ESO Records Search portal: {ESO_SEARCH_URL}...")
        page.goto(ESO_SEARCH_URL, wait_until="networkidle", timeout=45000)

        self._log(f"Applying date filters: {eso_start} to {eso_end}...")
        self._apply_search_date_filters(page, eso_start, eso_end)

        # Allow network activity to settle after filtering
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        # 3. Expand search grid page size to 100 to minimize pagination overhead
        page_size_select = page.locator("select.page-size-select, select[class*='page-size']")
        if page_size_select.count() > 0:
            try:
                self._log("Setting search grid page size to 100 records...")
                page_size_select.first.select_option("100")
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
            except Exception:
                pass

        self._log("Scanning incidents...")

        # Harvest rows across pages (handles date ranges with 100+ incidents)
        page_num = 1
        max_pages = 25
        while page_num <= max_pages:
            try:
                page.locator("table tbody tr, div.k-grid-content tr, div.record-row").first.wait_for(state="attached", timeout=4000)
            except Exception:
                pass

            rows = page.locator("table tbody tr, div.k-grid-content tr, div.record-row").all()

            for idx, row in enumerate(rows):
                link = row.locator("a[href*='/records/']").first
                href = link.get_attribute("href") if link.count() > 0 else ""
                record_id = None
                if href:
                    match = re.search(r"/records/(\d+)", href)
                    if match:
                        record_id = match.group(1)

                text = row.inner_text()
                tokens = [t.strip() for t in text.split("\t") if t.strip()]
                if not tokens:
                    tokens = [t.strip() for t in text.split("\n") if t.strip()]

                if len(tokens) >= 1:
                    inc_num = tokens[0]
                    inc_date_candidate = tokens[1] if len(tokens) > 1 else None

                    is_inactive_token = any("INACTIVE" in t.upper() for t in tokens)
                    init_status = "INACTIVE" if is_inactive_token else "ACTIVE"

                    # Note: in ESO grid, tokens[2] is the record Status ('IN REVIEW', 'DRAFT', 'INACTIVE'), NOT the Incident Type.
                    # Initialize incident_type as "Unknown Incident Type" so authoritative core API fills it.
                    if inc_num not in self.intercepted_incidents:
                        self.intercepted_incidents[inc_num] = Incident(
                            incident_number=inc_num,
                            incident_type="Unknown Incident Type",
                            incident_date=inc_date_candidate,
                            record_id=record_id,
                            status=init_status,
                        )
                        if record_id:
                            self.record_id_to_inc_num[record_id] = inc_num
                    else:
                        if record_id:
                            self.intercepted_incidents[inc_num].record_id = record_id
                            self.record_id_to_inc_num[record_id] = inc_num
                        if inc_date_candidate and not self.intercepted_incidents[inc_num].incident_date:
                            self.intercepted_incidents[inc_num].incident_date = inc_date_candidate
                        if is_inactive_token:
                            self.intercepted_incidents[inc_num].status = "INACTIVE"

            # Check for next page
            next_btn = page.locator("button[title='Next page'], a[title='Next page'], button:has-text('Next page')").first
            if next_btn.count() > 0 and next_btn.is_enabled():
                disabled_attr = next_btn.get_attribute("disabled")
                class_attr = next_btn.get_attribute("class") or ""
                if disabled_attr is not None or "disabled" in class_attr:
                    break
                next_btn.click()
                page_num += 1
                try:
                    page.wait_for_load_state("networkidle", timeout=6000)
                except Exception:
                    pass
            else:
                break

        self._log("Scanning incidents complete.")
        active_cnt = sum(1 for inc in self.intercepted_incidents.values() if inc.status != "INACTIVE" and not is_uuid(inc.incident_number))
        inactive_cnt = sum(1 for inc in self.intercepted_incidents.values() if inc.status == "INACTIVE" and not is_uuid(inc.incident_number))
        self._log(f"Found {active_cnt + inactive_cnt} total incident records ({active_cnt} active emergency calls, {inactive_cnt} inactive/drafts).")

        # 4. Stage 2: Rapidly drill down into Resources & Personnel using direct API requests
        incidents_to_drill = [
            inc for inc in self.intercepted_incidents.values()
            if inc.record_id and not inc.details_fetched
        ]

        if incidents_to_drill:
            self._log(f"Extracting responding apparatus and personnel rosters for {len(incidents_to_drill)} incidents...")
            self._fetch_records_batch(page, incidents_to_drill)
        else:
            self._log("All incident rosters and apparatus already harvested.")

        self._log("Personnel and apparatus extraction complete.")

        # Remove any lingering UUIDs or invalid records
        valid_incidents = [
            inc for inc in self.intercepted_incidents.values()
            if not is_uuid(inc.incident_number) and inc.incident_number != "Unknown"
        ]

        return valid_incidents

    def _fetch_records_batch(self, page: Page, incidents: List[Incident]):
        """
        Fetches incident records concurrently using ThreadPoolExecutor with persistent
        HTTP keep-alive connections and active session cookies, falling back to sequential
        Playwright API requests if needed.
        """
        try:
            cookies = self.context.cookies()
            if cookies and isinstance(cookies, list) and len(incidents) > 1:
                cookie_str = "; ".join(
                    f"{c['name']}={c['value']}"
                    for c in cookies
                    if isinstance(c, dict) and "name" in c and "value" in c
                )
                if cookie_str:
                    import concurrent.futures

                    from urllib.parse import urlparse
                    target_host = urlparse(ESO_SEARCH_URL).netloc or "www.esosuite.net"

                    try:
                        user_agent = page.evaluate("() => navigator.userAgent")
                    except Exception:
                        if sys.platform == "win32":
                            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
                        else:
                            user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

                    headers = {
                        "Cookie": cookie_str,
                        "Accept": "application/json",
                        "User-Agent": user_agent,
                        "Connection": "keep-alive",
                    }

                    # Partition incidents across worker threads to reuse HTTP connections
                    num_workers = min(8, len(incidents))
                    chunks: List[List[Incident]] = [[] for _ in range(num_workers)]
                    for idx, inc in enumerate(incidents):
                        chunks[idx % num_workers].append(inc)

                    def _fetch_chunk(batch: List[Incident]) -> List[Incident]:
                        failed: List[Incident] = []
                        if not batch:
                            return failed

                        conn = None
                        try:
                            conn = http.client.HTTPSConnection(target_host, timeout=12)
                            for inc in batch:
                                success = False
                                for attempt in range(3):
                                    if attempt > 0:
                                        time.sleep(0.3 * attempt)
                                    try:
                                        if conn is None:
                                            conn = http.client.HTTPSConnection(target_host, timeout=12)
                                        conn.request("GET", f"/fireincidents/api/incident/{inc.record_id}", headers=headers)
                                        resp = conn.getresponse()
                                        if resp.status == 200:
                                            raw_body = resp.read()
                                            payload = json.loads(raw_body.decode("utf-8"))
                                            self._parse_incident_dict(payload)
                                            success = True
                                            break
                                        else:
                                            try:
                                                resp.read()
                                            except Exception:
                                                pass
                                            # Reset connection on non-200 and retry
                                            try:
                                                conn.close()
                                            except Exception:
                                                pass
                                            conn = None
                                    except Exception as ex:
                                        logger.debug("Transient error fetching record %s (attempt %d): %s", inc.record_id, attempt, ex)
                                        if conn:
                                            try:
                                                conn.close()
                                            except Exception:
                                                pass
                                            conn = None
                                if not success:
                                    failed.append(inc)
                        finally:
                            if conn:
                                try:
                                    conn.close()
                                except Exception:
                                    pass
                        return failed

                    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                        chunk_results = list(executor.map(_fetch_chunk, chunks))

                    all_failed = [inc for chunk_res in chunk_results for inc in chunk_res]
                    for inc in all_failed:
                        self._fetch_record_api(page, inc)
                    return
        except Exception:
            pass

        for inc in incidents:
            self._fetch_record_api(page, inc)

    def _fetch_record_api(self, page: Page, incident: Incident):
        """
        High-performance direct API call to fetch full incident record including
        resources2.units and core data in ~50ms per incident.
        """
        api_url = f"https://www.esosuite.net/fireincidents/api/incident/{incident.record_id}"
        try:
            resp = page.request.get(api_url, timeout=12000)
            if resp.ok and "application/json" in resp.headers.get("content-type", ""):
                payload = resp.json()
                self._parse_incident_dict(payload)
                incident.details_fetched = True
                return
        except Exception as e:
            logger.debug("Direct API request failed for incident %s (%s): %s", incident.incident_number, incident.record_id, e)

        # Fallback to browser navigation if direct API fails
        self._extract_record_browser_fallback(page, incident)

    def _extract_record_browser_fallback(self, page: Page, incident: Incident):
        """Browser navigation fallback if API direct GET is unavailable."""
        resources_url = f"https://www.esosuite.net/fireincidents/records/{incident.record_id}/resources"
        try:
            page.goto(resources_url, wait_until="networkidle", timeout=25000)
            incident.details_fetched = True
        except Exception as e:
            logger.warning(f"Fallback navigation error for {incident.incident_number}: {e}")

    def _apply_search_date_filters(self, page: Page, start_date: str, end_date: str):
        """
        Handles date filter interaction. Opens the 'Filters' panel if needed
        and sets custom date range using modern non-deprecated Playwright input methods.
        """
        # If Filters button exists, open the Filters drawer if date inputs are not currently visible
        filters_btn = page.locator("button:has-text('Filters'), a:has-text('Filters')").first
        start_input = page.locator("input[name*='start' i], input[id*='start' i], input[placeholder*='Start' i]").first

        if filters_btn.count() > 0 and (start_input.count() == 0 or not start_input.is_visible()):
            try:
                filters_btn.click()
                start_input.wait_for(state="visible", timeout=3000)
            except Exception:
                pass

        # Check for preset dropdown / button (e.g. "Past 7 Days")
        preset = page.locator("button:has-text('Past 7 Days'), button:has-text('Last 7 Days'), [role='combobox']:has-text('Past 7 Days')").first
        if preset.count() > 0:
            try:
                preset.click()
                custom_opt = page.locator("text='Custom', [role='option']:has-text('Custom')").first
                if custom_opt.count() > 0:
                    custom_opt.click()
            except Exception:
                pass

        # Fill start date using modern Playwright press_sequentially
        start_input = page.locator("input[name*='start' i], input[id*='start' i], input[placeholder*='Start' i]").first
        if start_input.count() > 0:
            start_input.click()
            start_input.fill("")
            start_input.press_sequentially(start_date, delay=15)
            start_input.press("Tab")

        # Fill end date using modern Playwright press_sequentially
        end_input = page.locator("input[name*='end' i], input[id*='end' i], input[placeholder*='End' i]").first
        if end_input.count() > 0:
            end_input.click()
            end_input.fill("")
            end_input.press_sequentially(end_date, delay=15)
            end_input.press("Tab")

        # Submit search
        search_btn = page.locator("button:has-text('Search'), button:has-text('Apply'), button[type='submit'], input[value='Search']").first
        if search_btn.count() > 0:
            console.print("[cyan]Triggering search submission...[/cyan]")
            search_btn.click()
            page.wait_for_load_state("networkidle", timeout=30000)


def generate_sample_incidents() -> List[Incident]:
    """
    Generates realistic synthetic ESO Suite incident records including
    apparatus assignments (Engine 15, POV, Station Standby, etc.) for testing.
    """
    incident_specs = [
        (
            "CO15202600401",
            "111 - Building fire",
            "10/17/2026 20:25",
            ["Adams, John", "Baker, Mike", "Clark, Robert", "Davis, Shawn", "Evans, Todd"],
            ["Engine 15", "Rescue 15", "POV"],
            {"Adams, John": "Engine 15", "Baker, Mike": "Engine 15", "Clark, Robert": "Rescue 15", "Davis, Shawn": "Rescue 15", "Evans, Todd": "POV"},
        ),
        (
            "CO15202600402",
            "321 - EMS call, excluding vehicle accident with injury",
            "10/17/2026 02:29",
            ["Adams, John", "Foster, Kevin"],
            ["Engine 15", "POV"],
            {"Adams, John": "Engine 15", "Foster, Kevin": "POV"},
        ),
        (
            "CO15202600403",
            "322 - Motor vehicle accident with injuries",
            "10/15/2026 17:19",
            ["Baker, Mike", "Clark, Robert", "Garcia, Luis", "Harris, Charles"],
            ["Engine 15", "Station Standby"],
            {"Baker, Mike": "Engine 15", "Clark, Robert": "Engine 15", "Garcia, Luis": "Station Standby", "Harris, Charles": "Station Standby"},
        ),
        (
            "CO15202600404",
            "142 - Brush or brush-and-grass mixture fire",
            "10/15/2026 17:11",
            ["Adams, John", "Baker, Mike", "Davis, Shawn", "Evans, Todd", "Foster, Kevin"],
            ["Engine 15", "POV"],
            {"Adams, John": "Engine 15", "Baker, Mike": "Engine 15", "Davis, Shawn": "POV", "Evans, Todd": "POV", "Foster, Kevin": "POV"},
        ),
        (
            "CO15202600405",
            "321 - EMS call, excluding vehicle accident with injury",
            "10/15/2026 17:05",
            ["Clark, Robert", "Garcia, Luis"],
            ["POV", "Station Standby"],
            {"Clark, Robert": "POV", "Garcia, Luis": "Station Standby"},
        ),
        (
            "CO15202600406",
            "733 - Smoke detector activation due to malfunction",
            "10/15/2026 15:09",
            ["Adams, John", "Baker, Mike"],
            ["Engine 15"],
            {"Adams, John": "Engine 15", "Baker, Mike": "Engine 15"},
        ),
        (
            "CO15202600407",
            "412 - Gas leak (natural gas or LPG)",
            "10/14/2026 19:25",
            ["Davis, Shawn", "Evans, Todd", "Harris, Charles"],
            ["Engine 15", "Station Standby"],
            {"Davis, Shawn": "Engine 15", "Evans, Todd": "Station Standby", "Harris, Charles": "Station Standby"},
        ),
        (
            "CO15202600408",
            "321 - EMS call, excluding vehicle accident with injury",
            "10/13/2026 20:22",
            ["Adams, John", "Foster, Kevin"],
            ["POV"],
            {"Adams, John": "POV", "Foster, Kevin": "POV"},
        ),
        (
            "CO15202600409",
            "111 - Building fire",
            "10/11/2026 20:32",
            ["Adams, John", "Baker, Mike", "Clark, Robert", "Davis, Shawn", "Evans, Todd", "Harris, Charles"],
            ["Engine 15", "Rescue 15", "POV", "Station Standby"],
            {"Adams, John": "Engine 15", "Baker, Mike": "Engine 15", "Clark, Robert": "Rescue 15", "Davis, Shawn": "Rescue 15", "Evans, Todd": "POV", "Harris, Charles": "Station Standby"},
        ),
        (
            "CO15202600410",
            "651 - Smoke scare, odor of smoke",
            "10/11/2026 16:41",
            ["Baker, Mike", "Clark, Robert"],
            ["Engine 15"],
            {"Baker, Mike": "Engine 15", "Clark, Robert": "Engine 15"},
        ),
    ]

    return [
        Incident(
            incident_number=num,
            incident_type=itype,
            incident_date=dt,
            record_id=f"1085{i:04d}",
            responders=resp,
            apparatus=app,
            person_apparatus=pa,
            details_fetched=True,
        )
        for i, (num, itype, dt, resp, app, pa) in enumerate(incident_specs, 1)
    ]
