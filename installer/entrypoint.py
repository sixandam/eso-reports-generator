"""
Application entrypoint script for PyInstaller packaging.
Imports and runs the ESO Suite Fire Incidents Report Generator within its proper package.
"""

import sys
from pathlib import Path

# Ensure src is in search path
root = Path(__file__).resolve().parent.parent
src = root / "src"
if src.is_dir() and str(src) not in sys.path:
    sys.path.insert(0, str(src))

from eso_reports.cli import main

if __name__ == "__main__":
    main()

