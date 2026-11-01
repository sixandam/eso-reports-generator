from pathlib import Path
from unittest.mock import MagicMock
from src.scraper import ESOScraper
from src.models import Incident


def test_parse_incident_dict_overwrites_status_with_core_type(tmp_path: Path):
    mock_context = MagicMock()
    debug_log = tmp_path / "debug.log"

    scraper = ESOScraper(
        context=mock_context,
        debug_log_path=debug_log,
    )

    # Simulate an incident initially created from grid tokens with "IN REVIEW" status
    scraper.intercepted_incidents["CO15202600407"] = Incident(
        incident_number="CO15202600407",
        incident_type="IN REVIEW",
        incident_date="09/28/2026 16:56:02",
        record_id="10194394",
    )

    # Simulate live ESO payload returned by _fetch_record_api
    payload = {
        "incidentId": 10194394,
        "core": {
            "incidentNumber": "CO15202600407",
            "incidentOnsetDateTime": "2026-09-28T16:56:02-04:00",
            "primaryIncidentTypeId": {
                "name": "Gas leak / gas odor",
                "value": 30,
            },
        },
        "resources2": {
            "units": [
                {
                    "unitId": {"name": "PMPR15"},
                    "personnel": [
                        {"agencyPerson": {"name": "Glass, Lucas | 1545"}},
                        {"agencyPerson": {"name": "Glass, Ryne | 1530"}},
                    ],
                }
            ]
        },
    }

    scraper._parse_incident_dict(payload)

    inc = scraper.intercepted_incidents["CO15202600407"]
    assert inc.incident_type == "Gas leak / gas odor"
    assert "PMPR15" in inc.apparatus
    assert "Glass, Lucas" in inc.responders
    assert "Glass, Ryne" in inc.responders


def test_format_date_for_eso():
    from src.scraper import format_date_for_eso
    assert format_date_for_eso("2026-09-01") == "09/01/2026"
    assert format_date_for_eso("2026/09/30") == "09/30/2026"
    assert format_date_for_eso("09/01/2026") == "09/01/2026"


def test_is_uuid():
    from src.scraper import is_uuid
    assert is_uuid("095140f5-fde5-ed11-a81c-000d3ae4ae10") is True
    assert is_uuid("CO15202600407") is False
    assert is_uuid("10852664") is False
    assert is_uuid("") is False


def test_scraper_logging_callback(tmp_path: Path):
    mock_context = MagicMock()
    debug_log = tmp_path / "debug.log"
    logs = []

    scraper = ESOScraper(
        context=mock_context,
        debug_log_path=debug_log,
        log_callback=lambda msg: logs.append(msg),
    )

    payload = {
        "incidentId": 10194394,
        "core": {
            "incidentNumber": "CO15202600444",
            "incidentOnsetDateTime": "2026-09-28T16:56:02-04:00",
        },
    }

    scraper._parse_incident_dict(payload)
    assert "Incident CO15202600444 found." in logs



