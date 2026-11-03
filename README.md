# ESO Reports Generator

An automated tool to export incident response records from ESO Suite RMS into clean, plain-text Excel workbooks (`.xlsx`) saved directly to your Desktop.

---

## Installation & Launch

### Windows
- **Installer (Recommended)**: Run `Windows/eso-reports-setup.exe` to install ESO Reports with Desktop and Start Menu shortcuts.
- **Portable**: Run `Windows/eso-reports-portable.exe` directly without installation.
- **From Source**: Run `python -m eso_reports.gui` in your terminal.

### Linux
1. Open a terminal in the project directory and run:
   ```bash
   ./Linux/setup.sh
   ```
2. Launch the application from your desktop launcher or run:
   ```bash
   ./Linux/run.sh
   ```

---

## How to Use

1. **Open Application**: Start **ESO Reports Generator**.
2. **Select Date Range**: Choose dates using the **Start Date** and **End Date** buttons, or click **This Month** / **Last Month**.
3. **Generate Report**: Click **Start report**.
4. **Sign In (First Run Only)**: A browser window will open if authentication is required. Log in with your ESO credentials and complete MFA (Duo/SMS). The browser closes automatically once authenticated.
5. **View Results**: When the status shows **Done**, open `ESO Report.xlsx` saved directly on your **Desktop**.
