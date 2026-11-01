# ESO Suite Fire Incidents Report Generator
**Lyn-Dan Heights Volunteer Fire Department**

An automated extraction and reporting tool designed for fire and rescue services to compile incident response records from [ESO Suite Records Management System (RMS)](https://www.esosuite.net/fireincidents/records/search) into clean, plain-text Excel workbooks (`.xlsx`) saved directly to your Desktop.

Built with a "zero upkeep" standard for departmental officers and administrative leadership: featuring self-healing session persistence, Duo/SMS MFA support, 30x faster direct API record harvesting, and a dark-mode graphical desktop application.

---

## Key Features

- **Modern Graphical Application**: Full-featured desktop application (PyQt6) with calendar date pickers, one-click month presets, and centered layout.
- **Direct API Acceleration**: High-performance backend JSON harvesting (`/api/incident/{record_id}`) fetching full personnel rosters and apparatus dispatches in milliseconds per incident with persistent connection pooling.
- **Seamless Authentication Lifecycle**: Persistent browser storage (`session.json`) in standard XDG configuration with strict file permissions (`0700` directory, `0600` file). If a session expires or MFA is required, an interactive browser automatically opens, allows authentication/Duo approval, saves the session, immediately closes, and resumes headlessly.
- **Plain-Text Excel Output**: Two dedicated sheets formatted cleanly without colored fills, frozen panes for scrolling (`D2` on Sheet 1, `A3` on Sheet 2), and automated column auto-fitting.
- **Roster & Inactive Call Segregation**: Automatically normalizes firefighter names (e.g. `Last, First`, stripping badge suffixes), aggregates attendance ratios, and segregates inactive/canceled draft entries to an audit log so attendance percentages remain accurate.

---

## Graphical User Interface (GUI)

Launch either via the double-clickable Desktop shortcut or from the terminal:

```bash
# Launch GUI directly
eso-reports-gui

# Or via application alias
eso-reports
```

### GUI Features & Layout
- **Department Branding Header**: Lyn-Dan Heights Volunteer Fire Department emblem displayed inline with the title.
- **Full Dark Mode**: Slate and charcoal theme (`#0F172A` / `#1E293B`) with high-contrast text and blue primary buttons.
- **Always Vertically Centered**: Control elements remain vertically centered in the window across all resizing operations.
- **Date Selectors & Popup Calendars**: Side-by-side Start and End date buttons anchored to clean Microsoft Forms / Fluent-style calendar popups for one-click date picking.
- **Month Presets**: One-click **Last Month** and **This Month** preset buttons.
- **Clean Execution UX**: A prominent centered **Start report** button. While running, an inline orange `In progress...` indicator displays. Upon completion, a bold green `Done` label with a two-lined vector checkmark displays without intrusive modal dialog popups. On failure, a clean red `Failed` indicator is displayed.
- **Expandable Terminal Diagnostic Log**: When the window is enlarged or maximized (height $\ge$ 640px), a live terminal output log appears below the controls showing daemon status and progress. In compact mode, the log cleanly collapses.

---

## Report Structure (`.xlsx`)

The generated report contains two dedicated sheets formatted according to departmental standards:

### Sheet 1: `Attendance Matrix`
A master cross-tabulation table linking incidents to responding personnel:
- **Header (Row 1)**: `Incident Number`, `Incident Type`, `Date`, followed by responding personnel sorted alphabetically (`Last, First`).
- **Incident Rows**:
  - `Column A`: CAD Incident Number (e.g., `CO15202600443`).
  - `Column B`: Official Primary Incident Type (e.g., `Motor vehicle collision`).
  - `Column C`: Dispatch / Onset timestamp (`MM/DD/YYYY HH:MM`).
  - `Columns D+`: Responders marked with `"X"`, missed calls left blank.
- **Summary Row (Row M+1)**:
  - `Column A`: `Total Calls Made`
  - `Column B`: `Total Incidents: M`
  - `Columns D+`: Individual metrics: `n/M (n%)` (e.g., `7/20 (35.0%)`).
- **Panes**: Columns A–C and Row 1 frozen (`D2` freeze panes) for horizontal and vertical scrolling.

### Sheet 2: `Incident Types & Apparatus`
A structured multi-section distribution report:
- **Section 1: Incident Types Breakdown (2 Columns)**:
  - `Column A`: Incident Type category.
  - `Column B`: Response frequency and percentage: `n/M (n%)`.
  - Verification row: `Total Incidents: M/M (100.0%)`.
- **Section 2: Apparatus / Resource Breakdown (2 Columns)**:
  - `Column A`: Apparatus or resource designation (`Engine 15`, `POV`, `Station Standby`, `Rescue 15`, etc.).
  - `Column B`: Calls made and percentage: `n/M (n%)`.
- **Section 3: Other / Inactive Reports Audit Log (2 Columns)**:
  - Captures draft, canceled, or unsubmitted calls segregated from active call percentages for departmental auditing.
- **Panes**: Header rows frozen (`A3` freeze panes).

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- Google Chrome or Chromium installed on the system

### 1. Set Up Virtual Environment

```bash
cd ~/Desktop/eso-reports-generator

python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

### 2. Desktop Shortcut Setup (Linux)

A ready-to-use desktop entry is available in `assets/eso-reports.desktop`:

```bash
# Install department icon for application launchers
mkdir -p ~/.local/share/icons
cp assets/ldhvfd_logo.png ~/.local/share/icons/ldhvfd_logo.png

# Install desktop shortcut into system menu
cp assets/eso-reports.desktop ~/.local/share/applications/

# Or copy directly to Desktop for one-click access:
cp assets/eso-reports.desktop ~/Desktop/
chmod +x ~/Desktop/eso-reports.desktop
```

### 3. Windows Standalone Build & Packaging

To export and compile the application for Windows with zero pre-requisites for end-users:

#### One-Click Local Build
On any Windows workstation with Python 3.10+ installed:
- Double-click `build_windows.bat` or run `.\build_windows.ps1` in PowerShell.

This automated script:
1. Sets up the virtual environment and installs dependencies (`PyQt6`, `openpyxl`, `playwright`, `pyinstaller`, `pillow`).
2. Generates the multi-resolution application icon (`assets/app_icon.ico`).
3. Runs PyInstaller with [`eso-reports.spec`](file:///home/sixandam/Desktop/eso-reports-generator/eso-reports.spec) to produce:
   - `dist/eso-reports-portable.exe` (Single-file portable executable).
   - `dist/eso-reports-windows.zip` (Portable ZIP archive).
4. Automatically invokes Inno Setup (if installed) to compile [`assets/installer.iss`](file:///home/sixandam/Desktop/eso-reports-generator/assets/installer.iss) into:
   - `dist/eso-reports-setup.exe` (Standard Windows installer wizard).

#### Cloud CI/CD Build
A GitHub Actions workflow is provided in [`.github/workflows/build-windows.yml`](file:///home/sixandam/Desktop/eso-reports-generator/.github/workflows/build-windows.yml). When committed to GitHub, it automatically compiles all three Windows distribution artifacts on Microsoft's native `windows-latest` cloud runners.

---

## Project Structure

```
reports/
├── assets/
│   ├── check.svg              # Vector completion checkmark
│   ├── eso-reports.desktop    # Desktop launcher configuration
│   └── ldhvfd_logo.png        # Lyn-Dan Heights VFD department crest
├── src/
│   ├── __init__.py            # Package metadata
│   ├── aggregator.py          # Attendance and frequency metric compiler
│   ├── auth.py                # Session persistence, browser launcher, & MFA
│   ├── cli.py                 # Click-based CLI entrypoint
│   ├── config.py              # Central application configuration & paths
│   ├── excel_exporter.py      # Plain-text OpenPyXL spreadsheet generator
│   ├── gui.py                 # PyQt6 dark-mode desktop GUI
│   ├── models.py              # Pydantic schemas & name normalization
│   └── scraper.py             # Playwright & REST API extraction engine
├── pyproject.toml             # Package configuration & entrypoints
├── requirements.txt           # Environment dependencies
└── README.md                  # Project documentation
```

---

## License & Department Notice

Proprietary tool configured specifically for Lyn-Dan Heights Volunteer Fire Department incident reporting. Ensure ESO Suite credentials and session tokens are protected in compliance with departmental security guidelines.
