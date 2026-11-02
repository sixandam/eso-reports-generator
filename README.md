# ESO Suite Fire Incidents Report Generator
**Lyn-Dan Heights Volunteer Fire Department**

An automated extraction and reporting tool designed for fire and rescue services to compile incident response records from [ESO Suite Records Management System (RMS)](https://www.esosuite.net/fireincidents/records/search) into clean, plain-text Excel workbooks (`.xlsx`) saved directly to your Desktop.

Built with a "zero upkeep" standard for departmental officers and administrative leadership: featuring cross-platform compatibility (Windows and Linux), self-healing session persistence, Duo/SMS MFA support, 30x faster direct API record harvesting, and a dark-mode graphical desktop application.

---

## Key Features

- **Cross-Platform Compatibility**: Fully supported and tested on both Windows (Windows 10/11) and Linux (Ubuntu/Debian and related distributions).
- **Modern Graphical Application**: Full-featured desktop application (PyQt6) with calendar date pickers, one-click month presets, and centered layout.
- **Direct API Acceleration**: High-performance backend JSON harvesting (`/api/incident/{record_id}`) fetching full personnel rosters and apparatus dispatches in milliseconds per incident with persistent connection pooling.
- **Seamless Authentication Lifecycle**: Persistent browser storage (`session.json`) in standard configuration directories (`%APPDATA%` on Windows, standard XDG configuration on Linux with `0700` directory and `0600` file permissions). If a session expires or MFA is required, an interactive browser automatically opens, allows authentication/Duo approval, saves the session, immediately closes, and resumes headlessly.
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
- **Date Selectors & Popup Calendars**: Side-by-side Start and End date buttons anchored to clean Fluent/Forms-style calendar popups for one-click date picking.
- **Month Presets**: One-click **Last Month** and **This Month** preset buttons.
- **Clean Execution UX**: A prominent centered **Start report** button. While running, an inline orange `In progress...` indicator displays. Upon completion, a bold green `Done` label with a two-lined vector checkmark displays without intrusive modal dialog popups. On failure, a clean red `Failed` indicator is displayed.
- **Expandable Diagnostic Log**: When the window is enlarged or maximized (height $\ge$ 640px), a live output log appears below the controls showing daemon status and progress. In compact mode, the log cleanly collapses.

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
- Google Chrome, Microsoft Edge, or Chromium installed on the system

### Linux Quickstart

#### One-Click Automated Setup
From the repository root, run the setup script:
```bash
bash scripts/setup_linux.sh
```
This automated script:
1. Creates a local Python virtual environment (`.venv`).
2. Installs dependencies and Playwright Chromium.
3. Installs the LDH department emblem into `~/.local/share/icons`.
4. Creates a desktop shortcut on your Desktop and system application menu.

#### Manual Setup (Linux)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
playwright install chromium
```

### Windows Quickstart

#### Option 1: Standalone Windows Setup Installer
For end users who do not have Python installed:
- Run `eso-reports-setup.exe` to install to `%LOCALAPPDATA%\Programs\ESO Reports` with Start Menu and Desktop shortcuts.
- No administrative privileges required.

#### Option 2: Local Developer Setup (Windows)
Open PowerShell or Command Prompt in the repository folder:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

---

## Building the Windows Installer (`setup.exe`)

To build the standalone Windows setup installer (`dist/eso-reports-setup.exe`):

### One-Click Build
Run either of the following from the project root:
```cmd
build.bat
```
or
```powershell
python scripts/build_installer.py
```

This automated script:
1. Verifies the multi-resolution application icon (`assets/app_icon.ico`).
2. Runs PyInstaller with [`installer/eso-reports.spec`](installer/eso-reports.spec) to package the application and dependencies into `dist/eso-reports/`.
3. Invokes Inno Setup (`ISCC.exe`) with [`installer/installer.iss`](installer/installer.iss) to compile `dist/eso-reports-setup.exe`.

### Installer Specifications
- **Per-User Installation**: Installs to `%LOCALAPPDATA%\Programs\ESO Reports` without requiring UAC/administrator elevation.
- **Self-Contained**: Bundles Python runtime and dependencies with solid LZMA2 compression (~59 MB total download).
- **System Browser Integration**: Uses built-in Microsoft Edge or Google Chrome for Playwright authentication, avoiding heavy external browser downloads.
- **Shortcuts & Uninstaller**: Installs Desktop and Start Menu shortcuts and registers a clean Windows uninstaller in Add/Remove Programs.

---

## Testing & Quality Assurance

Run the comprehensive unit test suite:

```bash
# Run all tests
pytest -v
```

All 42 unit tests cover data models, aggregator math, Excel rendering, Windows path discovery (including OneDrive), authentication lifecycle, and Qt user interface states.

---

## Project Structure

```
eso-reports-generator/
├── .github/
│   └── workflows/
│       └── test.yml           # Cross-platform CI test workflow
├── assets/
│   ├── app_icon.ico           # Multi-resolution Windows application icon
│   ├── check.svg              # Vector completion checkmark
│   ├── eso-reports.desktop    # Linux desktop launcher configuration
│   └── ldhvfd_logo.png        # Lyn-Dan Heights VFD department crest
├── installer/
│   ├── eso-reports.spec       # Clean PyInstaller specification
│   └── installer.iss          # Inno Setup Windows installer specification
├── scripts/
│   ├── build_installer.py     # Windows PyInstaller & Inno Setup compiler script
│   ├── make_icon.py           # Multi-resolution ICO generator
│   └── setup_linux.sh         # Linux one-click setup script
├── src/
│   └── eso_reports/
│       ├── __init__.py        # Package exports & metadata
│       ├── aggregator.py      # Attendance and frequency metric compiler
│       ├── auth.py            # Session persistence, browser launcher, & MFA
│       ├── cli.py             # CLI entrypoint
│       ├── config.py          # Central cross-platform configuration & paths
│       ├── excel_exporter.py  # Plain-text OpenPyXL spreadsheet generator
│       ├── gui.py             # PyQt6 dark-mode desktop GUI
│       ├── models.py          # Pydantic schemas & name normalization
│       └── scraper.py         # Playwright & REST API extraction engine
├── tests/
│   ├── __init__.py
│   ├── test_aggregator.py     # Aggregator and roster tests
│   ├── test_auth.py           # SessionManager and authentication tests
│   ├── test_cli.py            # CLI entrypoint tests
│   ├── test_excel_exporter.py # Excel formatting and sheet tests
│   ├── test_gui.py            # PyQt6 GUI and calendar tests
│   ├── test_scraper.py        # Scraping and date parsing tests
│   └── test_windows.py        # Windows path resolution and browser detection tests
├── .gitattributes             # Line ending normalization & binary definitions
├── .gitignore                 # Version control exclusions
├── build.bat                  # One-click Windows build batch wrapper
├── pyproject.toml             # Modern PEP 621 package metadata & configuration
├── requirements.txt           # Core runtime dependencies
├── requirements-dev.txt       # Development and test dependencies
└── README.md                  # Project documentation
```

---

## License & Department Notice

Configured for Lyn-Dan Heights Volunteer Fire Department incident reporting. Ensure ESO Suite credentials and session tokens are protected in compliance with departmental security guidelines.
