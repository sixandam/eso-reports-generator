#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f ".venv/bin/eso-reports-gui" ]; then
    echo "ESO Reports environment not initialized. Running setup first..."
    ./Linux/setup.sh
fi

if [ -f ".venv/bin/eso-reports-gui" ]; then
    exec .venv/bin/eso-reports-gui "$@"
elif command -v eso-reports-gui >/dev/null 2>&1; then
    exec eso-reports-gui "$@"
elif [ -f ".venv/bin/python" ]; then
    exec .venv/bin/python -m eso_reports.gui "$@"
else
    for cmd in python3.12 python3.11 python3.10 python3; do
        if command -v "$cmd" >/dev/null 2>&1; then
            exec "$cmd" -m eso_reports.gui "$@"
        fi
    done
    echo "[ERROR] Python environment not found. Please run ./Linux/setup.sh first."
    exit 1
fi

