"""
ESO Suite Fire Incidents Report Automation package.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .models import Incident, ReportDataset
from .aggregator import build_report_dataset
from .excel_exporter import export_report_to_excel
from .auth import SessionManager
from .scraper import ESOScraper

__all__ = [
    "__version__",
    "Incident",
    "ReportDataset",
    "build_report_dataset",
    "export_report_to_excel",
    "SessionManager",
    "ESOScraper",
]

