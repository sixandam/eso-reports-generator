# ESO Suite Fire Incidents Report Automation — Project Plan

## 1. Project Overview & Objective

This project automates the extraction and synthesis of fire incident reports from the **ESO Suite Records Management System** ([https://www.esosuite.net/fireincidents/records/search](https://www.esosuite.net/fireincidents/records/search)) for any specified date range.

The extracted data is processed and formatted into an automated Excel spreadsheet (`.xlsx`) containing two dedicated sheets:
1. **Attendance Matrix (Output 1):** An incident-by-incident matrix showing which personnel responded to ("made") each call, with summary statistics ("n/n (n%)") for each member at the bottom.
2. **Incident Types Summary (Output 2):** A frequency distribution and percentage breakdown of all incident types received during the period, formatted as `"Incident Type: n/n (n%)"`.

---

## 2. Detailed Output Specifications

### Sheet 1: `Attendance Matrix` (Output 1)
A cross-tabulation matrix of incidents versus personnel.

* **Headers (Row 1):**
  * `Column A`: **Incident Number** (e.g., `CO15202600443`)
  * `Column B`: **Incident Type** (e.g., `Motor vehicle collision`, `Fire / smoke alarm`)
  * `Column C`: **Date** (e.g., `10/17/2026 20:25`)
  * `Columns D to N`: **Personnel Names** (e.g., `Andreas, Kaitlyn`, `Christian, Michael`, sorted alphabetically)
* **Incident Rows (Rows 2 to M):**
  * One row per incident in chronological or numerical order.
  * Cells under personnel columns contain:
    * `"X"`: If the individual was dispatched / responded / made the call.
    * Empty / Blank (`""`): If the individual did not make the call.
* **Summary Row (Row M+1):**
  * `Column A`: `"Total Calls Made"`
  * `Column B`: `"Total Incidents: M"`
  * `Column C`: Blank (`""`)
  * `Columns D to N`: Formatted attendance metrics:
    $$\text{Total Calls Made} / \text{Total Incidents} \quad (\text{Percentage})$$
    * Example: `7/20 (35.0%)`
* **Formatting:**
  * Clean plain-text formatting (no colored fills, no decorative styles, pure text).
  * Auto-adjusted column widths.
  * Frozen headers (Row 1) and frozen columns A, B, and C (`D2` freeze panes) for horizontal scrolling.

---

### Sheet 2: `Incident Types & Apparatus` (Output 2)
A 2-column distribution table containing two stacked breakdown sections:

#### Section 1: Incident Types Breakdown (2 Columns)
* `Column A`: **Incident Type** (e.g., `Motor vehicle collision`)
* `Column B`: **Total Calls Made (%)**: Formatted as `n/N (n%)`
  * Example: `6/20 (30.0%)`
  * Example: `2/20 (10.0%)`
* Bottom verification row: `Total Incidents` in Col A, `N/N (100.0%)` in Col B.

#### Section 2: Apparatus / Unit Response Breakdown (2 Columns)
* Tracks all responding apparatus and resources (e.g., `Station Standby`, `PMPR15`, `POV`, `CMD15`, `ENG15`):
* `Column A`: **Apparatus / Resource** (e.g., `Station Standby`, `Engine 15`, `POV`)
* `Column B`: **Total Calls Made (%)**: Formatted as `n/N (n%)`
  * Example: `Station Standby: 9/20 (45.0%)`
  * Example: `PMPR15: 7/20 (35.0%)`
  * Example: `POV: 6/20 (30.0%)`
* **Formatting:**
  * Plain text formatting throughout (no colored fills).

---

## 3. Technical Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────┐
│                   CLI / User Input                     │
│  - Testing default: 09/01/2026 - 09/30/2026            │
│  - Default Output: ~/Desktop/fire_incidents_report.xlsx│
│  - Run command with no arguments for simplicity        │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│             Authentication & Browser Layer             │
│        (User's Default Browser / Persistent Profile)   │
│  - Use system default browser (LibreWolf / Chromium)   │
│  - Interactive MFA/SSO on first run                    │
│  - Reusable cookies & tokens in .session_state.json    │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│             Extraction & Scraping Engine               │
│  - Step 1: Records Search (09/01/2026 - 09/30/2026)    │
│    - Format dates as MM/DD/YYYY                        │
│    - Collect incident metadata & internal IDs          │
│  - Step 2: Record Drilldown (Resources > Personnel)    │
│    - Open Incident Report > Resources tab              │
│    - Extract responding personnel & apparatus          │
│      (e.g., Engine 15, POV, Station Standby)           │
│  - Step 3: Streamlined direct extraction (no caches)  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│             Data Transformation & Metrics              │
│  - Deduplicate & normalize personnel names             │
│  - Construct binary attendance matrix (X / Blank)      │
│  - Calculate member metrics: n/N (n%)                  │
│  - Calculate incident type distribution: n/N (n%)      │
│  - Calculate apparatus stats: <Unit>: n/N (n%)         │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│             Excel Report Generation Engine             │
│                      (openpyxl)                        │
│  - Pure plain-text rendering (no color fills)          │
│  - Sheet 1: Attendance Matrix                          │
│  - Sheet 2: Incident Types & Apparatus Breakdown       │
│  - Auto-fit columns & frozen panes                     │
│  - Write directly to ~/Desktop                         │
└────────────────────────────────────────────────────────┘
```

### Technology Selection:
* **Python 3.10+**: Core programming language.
* **Playwright (`playwright`)**: Modern, high-performance browser automation.
  * Connects with the user's default browser (LibreWolf / system Chromium) via executable path or persistent user context.
  * Supports interactive headful login for Agency Code, Username, Password, and Two-Factor Authentication (MFA/DUO).
  * Saves `storage_state` (cookies, local storage, auth tokens) to eliminate repeated logins.
  * Intercepts backend API requests (`page.on('response', ...)`) to extract raw structured JSON data directly when navigating incident resources.
* **openpyxl**: Excel workbook manipulation, generating unstyled plain-text tables with frozen panes.
* **Pydantic**: Type-safe schema validation for incident models, apparatus responses, and roster data.
* **Rich / Click**: Terminal UI with simple zero-argument testing defaults.

---

## 4. ESO Suite Integration Details

### Authentication Flow
1. **Interactive First Login**: ESO Suite mandates an Agency ID / Tenant, Username, Password, and frequently Multi-Factor Authentication (MFA). The program launches the user's browser if no valid session token exists, allowing the user to authenticate manually.
2. **Session Persistence**: Session tokens and cookies are saved to a protected local state file (`.session_state.json`). Subsequent executions operate in headless mode without prompting for credentials until session expiration.

### Search Navigation & Date Input Handling
1. Navigate directly to `https://www.esosuite.net/fireincidents/records/search`.
2. **Date Input Formatting**:
   * ESO Suite input fields require **`MM/DD/YYYY`** format (e.g. `09/01/2026` and `09/30/2026`).
   * When standard ISO dates (`2026-09-01`) were typed, ESO Suite rejected or ignored the input, causing the search grid to revert to its default "Past 7 days" filter (incidents from 10/10 to today).
   * Input clearing and event dispatching (`input`, `change`, `blur`) ensures the date range takes effect properly.

### Personnel & Apparatus Extraction (Incident Report > Resources > Personnel)
1. **Data Location & Hierarchy**: Responding personnel and their apparatus assignments are located inside each individual record at:
   $$\text{Incident Report} \longrightarrow \text{Resources} \longrightarrow \text{Personnel}$$
2. **Extraction Process**:
   * For each incident returned by the search grid, fetch its detailed resource data (either by intercepting the internal ESO REST API call `/resources` or `/personnel`, or by navigating into the record's Resources tab).
   * **Direct In-Memory Pipeline (No Checkpointing)**: Scraped records are held in memory directly for report generation. No intermediate cache files (`data_checkpoint.json`) are kept. If an extraction fails, errors are reported with plain-English clarity in the logs and the user restarts the run, guaranteeing clean, non-stale data every time.

### Live Run Analysis & Diagnosis (from ~/Desktop/fire_incidents_report.xlsx & ~/data_checkpoint.json)
Analysis of the live execution generated on the Desktop revealed four concrete findings:
1. **Duplicate Records & Incident Numbers**:
   * The DOM parser captured incidents by CAD number (e.g., `CO15202600443`), but in the search table, Column 2 is the timestamp (`10/17/2026 20:25:06`), not the incident type.
   * When drilling into records, ESO's backend payload returns the internal ID as `incidentId` (`10852664`), while the CAD number is located at `core.incidentNumber` (`CO15202600443`) and the real incident type is at `core.primaryIncidentTypeId.name` (`Other Alarm`).
   * Because `core.incidentNumber` was not referenced, the API parser created 20 duplicate entries with `incident_number = 10852664` and `incident_type = Unknown Incident Type`.
2. **Apparatus Structure (`resources2.units`)**:
   * The live ESO payload houses units and responders under `resources2.units` (rather than top-level `resources` or `apparatus`).
   * Each unit provides `unitId.name` (e.g. `POV`, `Station Standby`, `Engine 15`, `Rescue 15`).
   * Attached crew members are located in `unit.personnel[].agencyPerson.name` (e.g., `Wellons, Charles | 1534`).
   * Updating the parser to read `resources2.units` will immediately populate the apparatus breakdown on Sheet 2 and associate each member with their assigned unit.
3. **Personnel Name Formatting**:
   * Names contain badge suffixes (e.g., `" | 1534"`). Stripping the badge number or standardizing to `Last, First` produces a clean attendance matrix header.
4. **Date Filtering**:
   * The ESO search form retained the default "Past 7 Days" filter (10/10 to 10/17) because date input events must interact with the date picker or select the "Custom" date range preset.

### Diagnostic & Debug Logging Plan (~/Desktop/debug.log)
To capture exact search page form behaviors and network payloads during development without cluttering the console:
* When running with `--debug` or in testing mode, write `~/Desktop/debug.log`.
* Log all form controls, dropdown values, date inputs, and button states on `/fireincidents/records/search`.
* Log captured API request/response URLs and payloads.
* This log is purely diagnostic and will be disabled in final production runs.

### Speed Optimization (Direct API Extraction vs. DOM Navigation)
* **Initial Bottleneck**: Navigating to `.../records/{record_id}/resources` via `page.goto` forced the browser to load all HTML, heavy CSS, JavaScript SPA bundles, and over 15 background dictionaries (shifts, stations, divisions, units, valuesets). Each incident took 3–5 seconds, totaling ~60–100 seconds for 20 calls.
* **Resolution**: The underlying incident payload is available directly at:
  $$\text{GET } \text{https://www.esosuite.net/fireincidents/api/incident/}\{record\_id\}$$
* Using Playwright's `page.request.get()` reuses the authenticated session context and fetches the JSON directly in ~50ms per incident.
* **Result**: Processing 20 records drops from ~60 seconds to **under 2 seconds** (a ~30x speedup), with full fallback to browser navigation if the direct endpoint is unreachable.

---

## 5. Implementation Roadmap & Milestones

### Phase 1: Environment Setup & Scaffolding
- [x] Initialize Python virtual environment with `pyproject.toml` / `requirements.txt`.
- [x] Install Playwright browser binaries (`playwright install chromium`).
- [x] Set up project structure:
  ```
  reports/
  ├── PLAN.md
  ├── README.md
  ├── requirements.txt
  ├── pyproject.toml
  ├── .gitignore
  ├── tests/
  │   ├── test_aggregator.py
  │   ├── test_excel_exporter.py
  │   └── test_cli.py
  └── src/
      ├── __init__.py
      ├── cli.py               # CLI entrypoint and argument parsing
      ├── auth.py              # ESO Suite login & session management
      ├── scraper.py           # Record search and roster extraction
      ├── models.py            # Data models (Incident, Person, Report)
      ├── aggregator.py        # Matrix creation and metric calculations
      └── excel_exporter.py    # openpyxl workbook creation & styling
  ```

### Phase 2: Authentication & Session Management (`auth.py`)
- [x] Implement Playwright persistent browser context.
- [x] Implement session validation check against `esosuite.net`.
- [x] Implement interactive login fallback when session is invalid or expired.
- [x] Implement secure local storage of session credentials.

### Phase 3: Scraping & Extraction Pipeline (`scraper.py`)
- [x] Implement date filter form population on `/fireincidents/records/search`.
- [x] Implement search execution and results grid listener.
- [x] Capture backend API response payloads and map `core.incidentNumber` and `core.primaryIncidentTypeId.name`.
- [x] Extract full responding roster and apparatus from `resources2.units` for each incident record.
- [x] Streamline extraction pipeline directly into memory (eliminate checkpointing complexity).
- [x] Add diagnostic logger writing to `~/Desktop/debug.log`.

### Phase 4: Data Processing & Metrics Engine (`aggregator.py`)
- [x] Normalize firefighter / personnel names, stripping badge suffixes (` | 1534`).
- [x] Build the complete department roster set across the queried period.
- [x] Assemble binary attendance matrix (True/False or 'X'/Empty).
- [x] Compute per-person statistics: total calls, department call percentage.
- [x] Aggregate incident counts by type and compute percentage of total incident volume.
- [x] Aggregate apparatus response statistics (`<Apparatus>: n/N (n%)`).

### Phase 5: Excel Generation (`excel_exporter.py`)
- [x] Create clean, plain-text workbook with two sheets: `"Attendance Matrix"` and `"Incident Types & Apparatus"`.
- [x] Populate Sheet 1 with headers, incident rows, and the formatted summary row (`n/N (n%)`).
- [x] Populate Sheet 2 with Incident Type breakdown and Apparatus response breakdown.
- [x] Apply visual formatting: freeze panes, auto-fit column widths, clean table borders.

### Phase 6: Testing, Edge Cases & Polish
- [x] Test with edge cases (zero calls for a member, mutual aid calls, uncategorized incident types).
- [x] Validate Excel output structure, cell formulas, and freeze panes.
- [x] Finalize CLI options (`--start-date`, `--end-date`, `--output`, `--headless`, `--demo`, `--roster-file`, `--gui`).
- [x] Comprehensive test suite with 100% pass rate (`pytest`).

---

## 6. Live Run vs. Checkpoint Run Diagnosis & Root Causes

### Why Model vs. User Runs Gave Different Outputs
1. **Model's Run (`--use-checkpoint`)**:
   - The model executed `./.venv/bin/eso-reports --use-checkpoint` to verify the Excel formatting and column restructuring (Date in Column C, 2-column layout on Sheet 2).
   - `--use-checkpoint` bypassed the live browser scraper and reprocessed cached records in `~/data_checkpoint.json`.
   - In that checkpoint, records originated directly from backend API JSON payloads where `incident_type` was mapped directly from `core.primaryIncidentTypeId.name` (e.g. `Motor vehicle collision`, `AIRCRAFT EMERGENCY`, `Fire / smoke alarm`).
2. **User's Run (`eso-reports` live execution)**:
   - The user ran `~/Desktop/repos/reports/.venv/bin/eso-reports`, which launched the live Playwright browser against `esosuite.net`.
   - The date filter for September 2026 was successfully applied (`09/01/2026 - 09/30/2026`).
   - However, two live-scraping discrepancies occurred:
     - **Issue 1 (Incident Type = "IN REVIEW")**: When reading the HTML table row tokens, token 2 was the *Record Status* (`IN REVIEW`), not the incident type. Because the merge logic only overwrote `target_incident.incident_type` if it was empty, contained `/`, or was `"Unknown Incident Type"`, the real type (`core.primaryIncidentTypeId.name`) returned by `_fetch_record_api` was blocked from overwriting `"IN REVIEW"`.
     - **Issue 2 (Only 20 of 57 Incidents Captured)**: ESO's search grid displays 20 items per page (`Showing 1 to 20 of 57 items` for September 2026). The scraper only collected the 20 visible rows on page 1 (`CO15202600407` to `CO15202600388`, spanning Sept 28 to Sept 19), missing the remaining 37 calls from Sept 19 to Sept 01 across pages 2 and 3.

---

## 7. Scraper Fixes & Resolution (Implemented & Verified)

### Fix 1: Prioritize Authoritative Core Incident Type
- **Implementation**:
  - In grid row harvesting, row token 2 (status) is no longer assigned as the incident type. Records are initialized with `"Unknown Incident Type"`.
  - In `_parse_incident_dict`, whenever `core_inc_type` is present (from `core.primaryIncidentTypeId.name` or `incidentTypeDescription`), it unconditionally updates `target_incident.incident_type`.
  - Status strings (`"IN REVIEW"`, `"DRAFT"`, `"INACTIVE"`, `"COMPLETED"`) are explicitly treated as overridable.
- **Result**: 100% of the 57 incidents now show genuine incident types (`Motor vehicle collision`, `Fire / smoke alarm`, `Gas leak / gas odor`, etc.).

### Fix 2: Search Grid Pagination & Page Size Expansion
- **Implementation**:
  - Automatically selects `100` on the search table's `select.page-size-select` dropdown upon loading filtered results.
  - Implemented multi-page loop using `button[title='Next page']` to handle date ranges with >100 incidents.
- **Result**: Successfully extracted all **57 incidents** for September 2026 (from Sept 28 down to Sept 01) in a single run.

---

## 8. Incident Analysis: Line 46 (`260905-134412-LDHVFD`)

### Diagnostic Breakdown
- **Incident Number**: `260905-134412-LDHVFD`
- **Record ID**: `9405651`
- **Creation Timestamp**: `2026-09-05 13:44:12`
- **Created By**: `cwellons` (Charles Wellons)
- **Status in ESO**: `INACTIVE` (`IncidentStatusTypeId: 4`)

### Why the Number Looks Different
- Standard 911/CAD dispatches imported into ESO receive county CAD incident numbers (e.g. `CO15202600407` for Campbell County / Co. 15).
- In ESO Suite, when a user manually clicks **"+ Add incident"** on the records page without a CAD import, ESO assigns an auto-generated temporary timestamp ID in the format:
  $$\text{YYMMDD-HHMMSS-<AGENCY>}$$
  Here: `260905` (Sept 5, 2026) - `134412` (1:44:12 PM) - `LDHVFD` (Lyn-Dan Heights Vol. Fire Dept).
- The user started the record, never selected an incident type or added apparatus/crew, and marked it `INACTIVE`.
- **Handling Specification (Sheet 2 Inactive Reports Section)**:
  - Keep inactive records tracked for total transparency, but segregate them from the active attendance calculations on Sheet 1.
  - **Sheet 1 (`Attendance Matrix`)**: Displays only active / completed dispatches so member attendance percentages are accurate and not diluted by abandoned drafts.
  - **Sheet 2 (`Incident Types & Apparatus`)**: Adds **Section 3: `OTHER / INACTIVE REPORTS`** directly below the Apparatus breakdown table.
  - Formatted in the same clean 2-column plain-text layout:
    - `Column A`: Incident Number & Status (e.g. `260905-134412-LDHVFD (INACTIVE)`)
    - `Column B`: Date & Description (e.g. `09/05/2026 13:44 - Draft / No crew assigned`)


---

## 9. Phase 7: Simple Graphical User Interface (GUI) Specification

### Objective
Provide an intuitive, standalone desktop graphical interface allowing department leadership to select a report date range with calendar/date selectors and generate the Excel report with a single click ("Go"), without touching terminal commands.

### User Experience & Layout
```
+-------------------------------------------------------------+
|               ESO Suite Fire Incident Reports               |
+-------------------------------------------------------------+
|                                                             |
|  Date Range:                                                |
|  [ Start Date:  09/01/2026 (calendar) ]                     |
|  [ End Date:    09/30/2026 (calendar) ]                     |
|                                                             |
|  Quick Presets:                                             |
|  [ Last Month ]   [ This Month ]   [ Year to Date ]         |
|                                                             |
|  Options:                                                   |
|  [x] Exclude Inactive / Cancelled drafts                    |
|                                                             |
|  [                      GO / GENERATE                      ] |
|                                                             |
|  Status: Ready.                                             |
|  [====================================] (Progress bar)      |
|                                                             |
|  [ Open Generated Report ]                                  |
+-------------------------------------------------------------+
```

### Implementation Status (Completed & Tested)
- [x] Implemented `src/gui.py` using `PyQt6` with start/end date calendar pickers, presets, progress bar, live log feed, and "Open Report" launcher.
- [x] Connected `--gui` flag to CLI (`src/cli.py`) and standalone command `eso-reports-gui`.
- [x] Added automated unit tests in `tests/test_gui.py` covering window initialization, date presets, and worker thread configuration (16/16 tests passing).
- [x] Inactive reports automatically segregated to Sheet 2 Section 3 with 2-column layout.

---

## 10. Bug Diagnosis & Planned Fix: GUI Worker SessionManager Error

### Error Details
```
ERROR: An error occurred:
'SessionManager' object has no attribute 'launch_authenticated_context'
```

### Root Cause Analysis
- In [`src/gui.py`](file:///home/sixandam/Desktop/repos/reports/src/gui.py#L48), `ScraperWorker.run()` invoked:
  ```python
  session_mgr = SessionManager()
  with session_mgr.launch_authenticated_context(headless=True) as (browser, context):
  ```
- In [`src/auth.py`](file:///home/sixandam/Desktop/repos/reports/src/auth.py#L112), the actual authentication method is:
  ```python
  def get_authenticated_context(self, playwright: Playwright, headless: bool = True, force_login: bool = False) -> BrowserContext:
  ```
  which expects an active Playwright instance (`sync_playwright()`), matching the pattern implemented in `src/cli.py`.

### Fix Implementation & Resolution (Implemented & Tested)
1. **Added `@contextmanager launch_authenticated_context()` in `src/auth.py`**:
   - Manages Playwright lifecycle cleanly and yields `(browser, context)`.
   - Automatically closes context, browser, and playwright on exit.
2. **Updated `src/gui.py`**:
   - Auto-resolves user's home directory `~/.session_state.json`.
   - Uses `launch_authenticated_context()` to seamlessly run the scrape in the background worker thread.
3. **Unit Test Coverage**:
   - Added `tests/test_auth.py` verifying context and browser closure. All 17 unit tests pass.

---

## 11. Phase 8: Streamlined Dark Mode GUI with Inline Form Popup Calendar

To maximize usability and clarity for fire department administration, the GUI follows a balanced Dark Mode 4-row structure:

### Theme & Aesthetics
- **Full Dark Mode**: Deep slate background (`#0F172A`), charcoal button containers (`#1E293B`), subtle borders (`#334155`), high-contrast text (`#F8FAFC`), and emergency blue accent (`#2563EB`).
- **Department Branding Header**: Inline horizontal layout placing a crisp, high-resolution transparent Lyn-Dan Heights Vol. Fire Department official emblem logo directly to the **left** of the title `"Lyn-Dan Heights ESO Reports"`.
- **Always Vertically Centered**: The entire controls container (Logo + Title + Buttons) is balanced by an equal-stretch top spacer (`self.top_space`) and bottom spacer (`self.bottom_space` / `self.log_window`). Regardless of window size (compact, enlarged, or full screen), the controls NEVER move to the top and remain strictly centered vertically on the window.
- **Unified 4-Button Styling (Rows 1 & 2)**: The first four buttons (`Start Date`, `End Date`, `Last Month`, `This Month`) share completely identical typography, color, padding, and border styles (same font family, size `13px`, weight `600`, background `#1E293B`, border `1px solid #334155`, text `#F8FAFC`, height `38px`). No font or styling differences exist between date buttons and month presets.
- **Microsoft Forms Style Standard Calendar Popup (`PopupCalendar`)**:
  - Replaces complex custom widgets with a clean, familiar Microsoft Forms / Fluent style date picker.
  - Standard month navigation header (`< Month Year >`).
  - Standard 7-column day header (`Su, Mo, Tu, We, Th, Fr, Sa`).
  - Standard day grid with subtle hover highlights, brand blue fill for the active selected day, and no week-number column or cluttered lines.
  - Anchored directly below the corresponding date button; dismisses on outside click or date selection.
- **Non-Intrusive Completion Feedback (No Popups)**:
  - Eliminates modal dialog prompts (`QMessageBox.question`) asking to open the report upon completion.
  - Finishes with a clean `Done.` entry in the terminal log.
  - Displays a clean green text status indicator with a check mark (`✓ Done.`) directly to the right of the `[ Start report ]` button.
- **Standard Linux-Style Process Logging**:
  - Terminal log strictly emulates clean Linux daemon/command output conventions:
    ```
    Starting report for [date] to [date]...
    Scanning incidents...
    Incident [incident number] found...
    Writing to [write location]...
    Done.
    ```
- **Conditional Log Display (Below Buttons)**: When the window has sufficient vertical room (height >= 640px, maximized, or full screen), the log window reveals in the space from below the buttons down to the bottom of the screen. In compact mode, the log is hidden.
- **Row 1 (Date Selectors Side by Side)**: `[ Start Date: MM/DD/YYYY ]` and `[ End Date: MM/DD/YYYY ]`.
- **Row 2 (Month Presets Side by Side)**: `[ Last Month ]` and `[ This Month ]` (identical styling to Row 1).
- **Row 3 (Execution & Status Row)**: Centered `[ Start report ]` button flanked on the right by the inline green checkmark indicator (`✓ Done.`).
- **Row 4 (Terminal Log Area)**: Positioned from below the buttons to the bottom of the screen when expanded.

---

## 12. Enterprise Reliability Architecture: "Zero-Upkeep" Standard

To ensure this reporting tool continues operating smoothly for department administration across years without developer maintenance, the codebase will adhere to six core architectural reliability pillars:

### Pillar 1: Self-Healing Authentication & Interactive Login
- **Resilience**: Cookies expire and MFA policies rotate. When credentials expire, the application must never crash or throw unhandled exceptions.
- **Mechanism**: The tool intercepts login redirects, automatically displays an interactive browser window prompting the user to log in and approve Duo/SMS MFA, captures the new session state, saves it to `~/.session_state.json`, and seamlessly resumes report generation.
- **Clean One-Click Workflow**: Clicking **"Start report"** automatically verifies the authentication state before running. If the session is missing or expired, it automatically opens an interactive browser window for the user to complete login and approve MFA, seamlessly continuing extraction without manual intervention. No standalone re-authentication buttons, menus, or extra clutter are needed.

### Pillar 2: Direct API Priority (Defense Against Web Redesigns)
- **Resilience**: Web UI layouts (HTML/CSS/Kendo UI components) change frequently, but backend JSON APIs (`/fireincidents/api/incident/{id}`) remain stable for backwards compatibility.
- **Mechanism**: The extraction pipeline prioritizes direct authenticated REST endpoints (`page.request.get`). HTML scraping is used strictly as a discovery layer for record IDs. If ESO restyles their buttons or table headers, the underlying API extractor continues functioning without modification.

### Pillar 3: Resilient Data Models & Schema Evolution
- **Resilience**: Future ESO updates may introduce new NERIS fields, remove legacy attributes, or alter date formats.
- **Mechanism**:
  - Pydantic models configured with `model_config = ConfigDict(extra="ignore")` and safe fallback defaults.
  - Multi-pattern parsing for CAD identifiers (county dispatches, mutual aid numbers, and manual timestamp drafts).
  - Explicit segregation of inactive/cancelled/abandoned drafts to Sheet 2 Section 3, protecting the integrity of the attendance matrix.

### Pillar 4: Zero-Fuss Automated Execution & Clear Log Explanations (No Doctor Mode)
- **Resilience**: Standalone "Doctor" or diagnostic modes add unnecessary complexity and friction for non-technical users.
- **Mechanism**: Doctor mode is completely eliminated. The application runs directly on command. If an issue occurs (unsupported browser, network failure, invalid credentials, Desktop permission locks, or Excel write errors), the exact cause and step-by-step resolution are explained clearly in the real-time GUI terminal log and `~/Desktop/debug.log`.

### Pillar 5: Direct Pipeline & Clean Restart Architecture (No Checkpointing)
- **Resilience**: Storing intermediate partial checkpoints introduces cache staleness, disk bloat, and state desynchronization.
- **Mechanism**: Checkpointing is eliminated. Every run executes a clean, authoritative extraction. If a run fails due to network disconnection or unexpected issues, the logs provide full diagnostic context and the user simply clicks "Start report" to start over. No partial caches or disk clutter.

### Pillar 6: Repository-Managed Zero-Terminal Desktop Distribution (.desktop Launcher)
- **Resilience**: Future administrative staff should never need to open a terminal or run bash commands, and setup files must not linger loose on the desktop.
- **Mechanism**:
  - The desktop launcher is maintained directly within the repository (`assets/eso-reports.desktop`) rather than loose on the desktop.
  - The launcher icon references the high-resolution transparent Lyn-Dan Heights emblem (`assets/ldhvfd_logo.png`).
  - Double-clicking the launcher immediately activates the virtual environment and launches the polished Dark Mode GUI.

---

## 13. Phase 9: Simplification, Code Health & Branding Polish Specification

### 1. Doctor Mode Removal
- [x] Completely removed `src/doctor.py`, `tests/test_doctor.py`, and the `--doctor` CLI flag from `src/cli.py`.
- **Rationale**: The tool executes directly; any environmental, network, browser, or authentication issues are clearly diagnosed and surfaced in the application logs without requiring a standalone diagnostic subcommand.

### 2. Streamlined Authentication (No Re-Auth Button)
- [x] Verified single entrypoint: clicking "Start report" acts as the single source of truth. It verifies session validity first; if invalid, it pops up the interactive browser window for the user to log in and approve Duo/SMS MFA, saving `.session_state.json` and continuing immediately without extra UI clutter.

### 3. Checkpointing Elimination
- [x] Removed `data_checkpoint.json` saving/loading from `src/scraper.py`, `src/cli.py`, and tests. In-flight failures are detailed in the log, and users simply initiate a clean run.

### 4. High-Resolution Transparent LDH Emblem & Horizontal Header
- [x] Replaced `assets/ldhvfd_logo.png` with a clean, high-resolution transparent background PNG (removing the low-resolution white square artifact and edge fringing).
- [x] Redesigned the GUI header in `src/gui.py` to use a `QHBoxLayout` placing the emblem directly to the left of the title `"Lyn-Dan Heights ESO Reports"`, vertically centered with proportional 56x56 sizing.

### 5. Repository-Managed Desktop Launcher
- [x] Moved the desktop launcher shortcut off of the Desktop and maintained inside the repository (`assets/eso-reports.desktop`).
- [x] Configured the launcher to use the high-resolution transparent LDH emblem (`assets/ldhvfd_logo.png`) as its icon and execute the virtualenv GUI entrypoint.

### 6. Code Health Cleanups
- [x] In `src/scraper.py`: Removed duplicate dead `page.close()` and `return valid_incidents` statements.
- [x] In `src/models.py`: Configured `model_config = ConfigDict(extra="ignore")` explicitly on all Pydantic models for schema evolution resilience.
- [x] In `README.md` & tests: Synchronized documentation, added tests for new layout and model resilience; 21/21 tests passing.

---

## 14. Phase 10: Final UX Refinement & Standardized Logging Specification (Completed & Tested)

### 1. Microsoft Forms Style Standard Calendar Popup
- [x] In `src/gui.py`, implemented Microsoft Forms / Fluent style popup calendar (`PopupCalendar`):
  - Clean chevrons (`‹` and `›`) on navigation buttons with icons removed.
  - Standard 7-column day layout (`Su, Mo, Tu, We, Th, Fr, Sa`).
  - No spinbox widget on year (`setDateEditEnabled(False)`).
  - No week numbers, no grid lines, smooth hover state, solid `#2563EB` day selection.
  - Compact size (300x240) anchored directly below the date button.

### 2. Unified 4-Button Styling (Rows 1 & 2)
- [x] In `src/gui.py`, made all 4 buttons (`Start Date`, `End Date`, `Last Month`, `This Month`) 100% identical in styling:
  - Removed `QPushButton#presetBtn` QSS overrides.
  - Set `setFixedHeight(40)` uniformly across all 4 buttons.
  - Uniform typography (13px, font-weight 600, color `#F8FAFC`, background `#1E293B`, border `#334155`).

### 3. Non-Intrusive Completion Feedback (No Modal Popups)
- [x] Removed `QMessageBox.question` popup completely.
- [x] In Row 3, directly to the right of `[ Start report ]`, added an inline status indicator:
  - While running: displays `"In progress..."` in orange (`#F97316`, bold).
  - On completion: displays `"Done"` (no period) in green (`#22C55E`, bold) followed by a two-lined vector SVG checkmark to its right (`assets/check.svg`).
  - Balanced with an equal 130px left spacer so `btn_start_report` remains mathematically centered.
  - Automatically resets when dates change or when "Start report" is clicked.

### 4. Standard Linux-Style Process Logging & Verbose Debugging Tells
- [x] Implemented in-depth, one-line Linux debugging tells for every stage of pipeline execution:
  - Date format matched to button display: `MM/DD/YYYY`.
  - Exact phrase on incident scan completion: `Scanning incidents complete.`.
  - Comprehensive authentication tells:
    - Saved session verification: `Checking saved session file: .session_state.json...` -> `Testing saved session validity...` -> `Navigating to https://www.esosuite.net/fireincidents/records/search...`.
    - Expiration & Re-auth tells: `Session redirected to login page. Saved session is expired.` -> `Authentication failed.` -> `Opening browser for re-authentication...` -> `Waiting for user credentials and multi-factor authentication (MFA)...` -> `Authentication success.` -> `Session state saved to .session_state.json.` -> `Closing interactive authentication browser...` -> `Initializing headless background browser...` -> `Done.`.
  - Search portal navigation and filter tells:
    - `Connecting to ESO Records Search portal: https://www.esosuite.net/fireincidents/records/search...`
    - `Applying date filters: MM/DD/YYYY to MM/DD/YYYY...`
    - `Setting search grid page size to 100 records...`
    - `Scanning incidents...`
    - `Incident CO15202600444 found.`
    - `Scanning incidents complete.`
    - `Found 23 total incident records (21 active emergency calls, 2 inactive/drafts).`
  - Granular apparatus and personnel extraction tells:
    - `Extracting responding apparatus and personnel rosters for 21 incidents...`
    - `Fetching personnel roster for incident CO15202600444 (ID: 10852664)...`
    - `Personnel and apparatus extraction complete.`
    - `Done.`
  - In-depth roster and attendance analysis tells:
    - `Analyzing rosters and attendance...`
    - `Normalizing personnel names and building department roster...`
    - `Compiling member attendance matrix across all active incidents...`
    - `Calculating individual member response counts and percentages...`
    - `Aggregating incident type breakdown and apparatus dispatch frequencies...`
    - `Segregating inactive and draft calls for administrative audit...`
    - `Identified 18 responders across 21 active calls (2 inactive/drafts).`
    - `Done.`
  - Structured Excel workbook generation tells:
    - `Writing to /home/user/Desktop/fire_incidents_report.xlsx...`
    - `Creating plain-text Excel workbook with two sheets...`
    - `Writing Sheet 1: Master Attendance Matrix (21 incidents x 18 personnel)...`
    - `Writing Sheet 2: Section 1 (Incident Types Breakdown, 5 categories)...`
    - `Writing Sheet 2: Section 2 (Apparatus Breakdown, 4 units)...`
    - `Writing Sheet 2: Section 3 (Other / Inactive Reports Audit Log, 2 records)...`
    - `Saving Excel workbook to /home/user/Desktop/fire_incidents_report.xlsx...`
    - `Workbook saved successfully.`
    - `Done.`

### 5. Interactive Browser Auto-Close & Lifecycle Isolation
- [x] In `src/auth.py`, configured `interactive_login`:
  - When re-authentication is required, launches a visible browser for user credentials and MFA.
  - As soon as authentication succeeds and storage state is saved to `.session_state.json`, closes the visible browser page, context, and browser instance immediately.
  - Launches a fresh, isolated background headless browser (`headless=True`) to perform scraping invisibly so the user cannot see or interfere with background page interactions.

### 6. Automated Test Coverage
- [x] Added unit tests across `tests/test_auth.py`, `tests/test_gui.py`, and `tests/test_scraper.py`:
  - `test_interactive_login_closes_visible_browser_and_returns_headless`: Asserts visible browser is closed upon saving storage state and headless browser is spawned.
  - `test_get_authenticated_context_expired_session_triggers_reauth`: Asserts session expiration triggers failure log and re-authentication.
  - `test_scraper_worker_logging_pipeline`: Asserts worker emits all in-depth debugging tells across authentication, scanning, analysis, and Excel writing.
  - `test_first_four_buttons_uniform_styling`: Verifies all 4 buttons have identical height and styles.
  - `test_completion_status_ux_no_prompt`: Verifies `In progress...` (orange) and `Done` + SVG checkmark (green) states and resets without modal dialogs.
  - `test_popup_calendar_ms_forms_style`: Verifies `‹` and `›` chevrons and disabled date edit spinbox.
  - `test_scraper_worker_date_format_and_pixmap`: Verifies MM/DD/YYYY date formatting and SVG pixmap loading.
- [x] 100% test pass rate (29/29 tests passing).

---

## 15. Phase 11: Windows Standalone Export & Packaging Architecture

### 15.1 Objective & Scope
Export the ESO Suite Fire Incidents Report Generator as a fully self-contained, standalone Windows application (`.exe`) that fire department administration can run on Windows 10 and Windows 11 with zero technical setup.

**Core Requirements:**
- **Zero Python / Terminal Pre-requisites**: Users do not need Python, Git, pip, or Node installed.
- **Native Windows Look & Feel**: High-DPI support, official LDH emblem icon in taskbar and executable metadata, seamless Dark Mode.
- **Zero Manual Browser Downloads**: Utilize native Windows Chromium engines (Microsoft Edge or Google Chrome) via Playwright channels (`channel="msedge"` / `channel="chrome"`) with fallback to bundled drivers.
- **OneDrive & Path Resilience**: Automatically detect the real active Windows Desktop (even when redirected to OneDrive) and use `%APPDATA%` for session persistence.
- **Dual Distribution Targets**:
  1. **Portable Standalone Executable (`eso-reports.exe`)**: Single double-clickable file for immediate use or USB deployment.
  2. **Standard Windows Installer Wizard (`eso-reports-setup.exe`)**: Built with Inno Setup, offering Start Menu shortcuts, Desktop icons, and clean uninstall capabilities without requiring administrator privileges.

---

### 15.2 Technical Gap Analysis: Linux vs. Windows Target

| Dimension | Current Linux Implementation | Windows Standalone Target | Architectural Solution |
| :--- | :--- | :--- | :--- |
| **Runtime Environment** | Linux venv (`python3.14`) | Standalone native Windows binary | PyInstaller bundle with embedded CPython 3.11/3.12 runtime |
| **Config & State Directory** | `~/.config/eso-reports` (`XDG_CONFIG_HOME`) | `%APPDATA%\eso-reports` (`Roaming`) | Add platform-aware `get_app_config_dir()` resolving Windows `%APPDATA%` |
| **Desktop Output Path** | `Path.home() / "Desktop"` | Active Windows Desktop (may be OneDrive synced) | Query Windows Registry `User Shell Folders` with fallback to `USERPROFILE\OneDrive\Desktop` |
| **File Permissions** | POSIX `chmod 0700` and `0600` | Windows NTFS Access Control Lists (ACL) | Gracefully bypass POSIX chmod on Windows via platform check |
| **Browser Engine** | `find_system_browser()` looks for `chromium`/`google-chrome` | Microsoft Edge (Chromium) is pre-installed on 100% of Windows 10/11 machines | Support Playwright's `channel="msedge"` and standard Windows `msedge.exe`/`chrome.exe` locations |
| **Asset Resolution** | `PROJECT_ROOT / "assets"` relative to `__file__` | PyInstaller temporary extraction folder (`sys._MEIPASS`) | Update asset loading via `get_resource_path()` supporting frozen `sys._MEIPASS` |
| **Taskbar & Window Icon** | System X11 / Wayland icon | Windows AppUserModelID & Multi-size `.ico` | Call `SetCurrentProcessExplicitAppUserModelID` via `ctypes` and build `assets/app_icon.ico` |
| **Console Window** | Terminal process | Hidden console / Windowed GUI (`noconsole`) | PyInstaller `console=False` so no black terminal window pops up |
| **Playwright Packaging** | Python package + local node driver | Packaged `playwright._impl._driver` (node.exe + cli) | Configure PyInstaller spec `--collect-all playwright` |

---

### 15.3 Architecture & Component Plan

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Windows End-User Workstation                      │
│                                                                        │
│  Double-click "eso-reports.exe"  (or Desktop Shortcut via Installer)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        PyInstaller Bootloader                          │
│  - Unpacks embedded runtime & assets to %TEMP%\_MEIxxxx (if onefile)   │
│  - Sets Windows AppUserModelID: "LDHVFD.ESOSuiteReports.App.1_0"       │
│  - Enables Qt High-DPI PassThrough Scaling                             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       PyQt6 Dark Mode GUI                              │
│  - Resolves assets via sys._MEIPASS: ldhvfd_logo.png, check.svg        │
│  - Resolves output path: %USERPROFILE%\OneDrive\Desktop or Desktop     │
│  - Resolves auth state: %APPDATA%\eso-reports\session.json             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      Authentication & Playwright                       │
│  - Bundled Playwright node.exe driver                                  │
│  - Browser Discovery Priority:                                         │
│    1. Microsoft Edge (System Chromium: channel="msedge")               │
│    2. Google Chrome (System Chromium: channel="chrome")                │
│    3. Windows Registry App Paths (msedge.exe / chrome.exe)             │
│  - Interactive Login window opens if session expired, then closes      │
│  - Headless background scraping continues                              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      Report Engine & Output                            │
│  - openpyxl writes clean plain-text workbook                           │
│  - Saves directly to active Windows Desktop                            │
│  - Optional one-click "Open Report" via Windows `os.startfile()`       │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 15.4 Detailed Code & Configuration Specifications

#### 1. Cross-Platform Configuration & Path Normalization (`src/config.py`)
- **Windows `%APPDATA%` Support**:
  ```python
  if sys.platform == "win32":
      appdata = os.environ.get("APPDATA")
      APP_CONFIG_DIR = Path(appdata) / APP_NAME if appdata else Path.home() / "AppData" / "Roaming" / APP_NAME
  else:
      XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
      APP_CONFIG_DIR = XDG_CONFIG_HOME / APP_NAME
  ```
- **Active Windows Desktop Discovery (Handling OneDrive Redirection)**:
  ```python
  def get_default_desktop_path() -> Path:
      if sys.platform == "win32":
          # 1. Try Windows Registry for active Desktop folder
          try:
              import winreg
              key = winreg.OpenKey(
                  winreg.HKEY_CURRENT_USER,
                  r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
              )
              desktop_dir, _ = winreg.QueryValueEx(key, "Desktop")
              winreg.CloseKey(key)
              expanded = os.path.expandvars(desktop_dir)
              if Path(expanded).exists():
                  return Path(expanded)
          except Exception:
              pass
          # 2. Check OneDrive Desktop
          user_profile = Path(os.environ.get("USERPROFILE", Path.home()))
          onedrive_desktop = user_profile / "OneDrive" / "Desktop"
          if onedrive_desktop.exists():
              return onedrive_desktop
      return Path.home() / "Desktop"
  ```
- **PyInstaller Frozen Asset Resolution**:
  ```python
  def get_resource_path(relative_path: str | Path) -> Path:
      if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
          return Path(sys._MEIPASS) / relative_path
      return PROJECT_ROOT / relative_path
  ```

#### 2. Native Windows Browser Discovery (`src/auth.py`)
- **System Edge & Chrome Strategy**:
  Microsoft Edge is based on Chromium and is guaranteed to be present on Windows 10/11. Playwright natively supports `playwright.chromium.launch(channel="msedge")`.
  ```python
  def find_system_browser() -> Optional[str]:
      if sys.platform == "win32":
          # Check standard Windows paths
          candidates = [
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
              os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
          ]
          for p in candidates:
              if Path(p).is_file():
                  return p
      else:
          for bin_name in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
              path = shutil.which(bin_name)
              if path:
                  return path
      return None
  ```
- **Playwright Launch Channel Integration**:
  If direct executable path is not resolved, fallback to `channel="msedge"` or `channel="chrome"` before failing.

#### 3. Windows Taskbar & High-DPI Integration (`src/gui.py`)
- **Explicit AppUserModelID**:
  ```python
  if sys.platform == "win32":
      try:
          import ctypes
          myappid = "LDHVFD.ESOSuiteReports.App.1_0"
          ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
      except Exception:
          pass
  ```
- **Multi-Resolution Windows Icon**:
  Generate `assets/app_icon.ico` containing sizes: 16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256.
  Set `app.setWindowIcon(QIcon(str(ICO_PATH)))`.

#### 4. PyInstaller Packaging Specification (`eso-reports.spec`)
A custom PyInstaller specification file ensuring Playwright's node.exe driver and assets are bundled cleanly:
```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('assets', 'assets'),
]
binaries = []
hiddenimports = [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtSvg',
    'openpyxl',
    'pydantic',
    'click',
    'rich',
]

# Collect all Playwright driver files and dependencies
p_datas, p_binaries, p_hiddenimports = collect_all('playwright')
datas += p_datas
binaries += p_binaries
hiddenimports += p_hiddenimports

a = Analysis(
    ['src/cli.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='eso-reports',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed GUI (no black console prompt)
    icon='assets/app_icon.ico',
)
```

#### 5. Windows Inno Setup Script (`assets/installer.iss`)
For departmental officers who prefer a traditional Windows installation wizard:
- Per-user installation (requires no administrator rights, writes to `%LOCALAPPDATA%\Programs\ESO Reports`).
- Installs `eso-reports.exe` and assets.
- Automatically creates:
  - Desktop Shortcut (`Lyn-Dan Heights ESO Reports`) with LDH emblem icon.
  - Start Menu entry under `Lyn-Dan Heights VFD`.
  - Clean uninstaller in Windows "Installed apps" settings.

---

### 15.5 Build Toolchain & CI/CD Strategy

Because cross-compiling Windows executables containing PyQt6 and Node.js binaries directly on Linux is inherently brittle, the project will implement two complementary build methods:

#### Method 1: Automated GitHub Actions CI/CD Cloud Build (Zero Setup Required)
A dedicated workflow `.github/workflows/build-windows.yml`:
1. Triggers automatically on git tags (`v*.*.*`) or manual trigger (`workflow_dispatch`).
2. Runs on native Microsoft runner (`windows-latest`).
3. Sets up Python 3.11 x64.
4. Installs dependencies and runs unit test suite (`pytest`).
5. Generates `app_icon.ico` from `ldhvfd_logo.png`.
6. Executes PyInstaller to generate `eso-reports.exe`.
7. Compiles Inno Setup script into `eso-reports-setup.exe`.
8. Uploads standalone executable and installer as downloadable build artifacts / GitHub Releases.

#### Method 2: Local Windows Build Script (`build_windows.bat`)
For local builds on any Windows machine:
```cmd
@echo off
echo Building ESO Suite Reports for Windows...
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt pyinstaller pillow
python scripts\make_icon.py
pyinstaller eso-reports.spec --clean --noconfirm
echo Build complete! Executable is at dist\eso-reports.exe
pause
```

---

### 15.6 Implementation Roadmap & Milestones

- [x] **Phase 11.1: Cross-Platform Path Hardening**
  - Updated `src/config.py` with `%APPDATA%` resolution, OneDrive Desktop discovery, and `get_resource_path()` for frozen bundles.
  - Safeguarded POSIX chmod calls in `src/config.py` and `src/auth.py`.
- [x] **Phase 11.2: Windows Browser Discovery & Playwright Channel Support**
  - Updated `find_system_browser()` in `src/auth.py` to support standard Windows Edge and Chrome locations and registry lookup.
  - Configured Playwright launch with fallback `channel="msedge"` to support zero-download execution.
- [x] **Phase 11.3: Windows Branding Assets & Icon Generation**
  - Created `scripts/make_icon.py` using Pillow and generated multi-resolution `assets/app_icon.ico` (16px to 256px) from `assets/ldhvfd_logo.png`.
  - Added AppUserModelID in `src/gui.py` to bind the LDH emblem to the Windows taskbar, along with Qt high-DPI PassThrough scaling.
- [x] **Phase 11.4: PyInstaller Specification & Bundling Verification**
  - Created `eso-reports.spec` configured for windowed GUI execution (`console=False`), bundling `assets/`, and collecting all Playwright node driver binaries.
  - Configured dual targets: `dist/eso-reports-portable.exe` and `dist/eso-reports/` directory.
- [x] **Phase 11.5: Inno Setup Installer Script**
  - Created `assets/installer.iss` for automated per-user Windows setup with Desktop and Start Menu shortcuts and uninstaller.
- [x] **Phase 11.6: Automated Build Scripts & GitHub Actions Windows Workflow**
  - Created `build_windows.bat` (batch script) and `build_windows.ps1` (PowerShell script) for one-click local builds on Windows.
  - Created `.github/workflows/build-windows.yml` to automatically compile native `.exe`, `.zip`, and installer artifacts on `windows-latest`.
- [x] **Phase 11.7: Documentation & Automated Testing**
  - Updated `README.md` with Windows installation and build instructions.
  - Added `tests/test_windows.py` covering Windows path resolution, OneDrive discovery, and browser detection.
  - Verified 100% test pass rate across all 40 unit tests.

---

### 15.7 User Decisions & Execution Summary

- **Packaging Preference**: Both (portable `.zip` and Inno Setup setup wizard `eso-reports-setup.exe`).
- **Build Execution**: Workstation handoff ready — local one-click scripts (`build_windows.bat`, `build_windows.ps1`) and cloud CI/CD workflow (`.github/workflows/build-windows.yml`) prepared for Google Drive export and Windows deployment.
- **Browser Engine Strategy**: Default to system Microsoft Edge / Google Chrome (pre-installed, keeping distribution download size compact at ~75MB).











