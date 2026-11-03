#!/usr/bin/env bash
set -e

# =====================================================================
# ESO Reports - Linux Setup & Desktop Integration Script
# =====================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "=== ESO Reports Setup ==="

# 1. Check Python
PYTHON_BIN=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON_BIN="$cmd"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] Python 3.10+ was not found on your system. Please install python3-venv."
    exit 1
fi

echo "[1/4] Using $PYTHON_BIN to create virtual environment..."
if [ ! -d ".venv" ]; then
    "$PYTHON_BIN" -m venv .venv
fi

echo "[2/4] Installing dependencies..."
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e .
./.venv/bin/playwright install chromium || true

echo "[3/4] Installing application icon..."
mkdir -p "$HOME/.local/share/icons"
if [ -f "assets/logo.png" ]; then
    cp assets/logo.png "$HOME/.local/share/icons/eso-reports.png"
elif [ -f "assets/ldhvfd_logo.png" ]; then
    cp assets/ldhvfd_logo.png "$HOME/.local/share/icons/eso-reports.png"
fi

echo "[4/4] Generating desktop launchers..."
mkdir -p "$HOME/.local/share/applications"

DESKTOP_ENTRY="[Desktop Entry]
Version=1.0
Type=Application
Name=ESO Reports Generator
Comment=Automated ESO Suite Incident Reports and Attendance Generator
Exec=$SCRIPT_DIR/.venv/bin/eso-reports-gui
Icon=eso-reports
Terminal=false
StartupNotify=true
Categories=Office;Spreadsheet;"

echo "$DESKTOP_ENTRY" > "$HOME/.local/share/applications/eso-reports.desktop"

if [ -d "$HOME/Desktop" ]; then
    echo "$DESKTOP_ENTRY" > "$HOME/Desktop/eso-reports.desktop"
    chmod +x "$HOME/Desktop/eso-reports.desktop" || true
fi

echo ""
echo "====================================================================="
echo " Setup complete!"
echo " You can launch the application by:"
echo " - Double-clicking the Desktop shortcut"
echo " - Running: ./Linux/run.sh or ./.venv/bin/eso-reports-gui"
echo "====================================================================="

