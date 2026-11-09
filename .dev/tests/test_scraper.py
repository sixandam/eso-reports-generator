from pathlib import Path
from unittest.mock import MagicMock
from eso_reports.scraper import ESOScraper
from eso_reports.models import Incident


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


def test_cad_notes_read_from_live_eso_structure():
    from eso_reports.models import Member
    scraper = ESOScraper(
        context=MagicMock(),
        members=[Member(name="Wellons, Charles", primary_id="1534", aliases=["1534"], active=True)],
    )
    scraper._parse_incident_dict({
        "incidentId": 10194400,
        "core": {"incidentNumber": "CO15202601000"},
        "cad": {"cadIncidentId": "abc", "streetAddress": "1 Main St", "cadNotes": "1534 EN ROUTE POV"},
    })

    inc = scraper.intercepted_incidents["CO15202601000"]
    assert inc.cad_notes == "1534 EN ROUTE POV"
    assert inc.radio_markups_found == ["1534"]
    assert inc.radio_responders == ["Wellons, Charles"]


def test_format_date_for_eso():
    from eso_reports.scraper import format_date_for_eso
    assert format_date_for_eso("2026-09-01") == "09/01/2026"
    assert format_date_for_eso("2026/09/30") == "09/30/2026"
    assert format_date_for_eso("09/01/2026") == "09/01/2026"


def test_is_uuid():
    from eso_reports.scraper import is_uuid
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


def test_scraper_auto_learn_badge_from_payload(tmp_path: Path):
    from eso_reports.models import Member
    mock_context = MagicMock()
    custom_members = [
        Member(name="Wellons, Charles", primary_id="1534", aliases=["1534"], active=True)
    ]

    scraper = ESOScraper(
        context=mock_context,
        members=custom_members,
    )

    payload = {
        "incidentId": 10194399,
        "core": {
            "incidentNumber": "CO15202600999",
            "incidentOnsetDateTime": "2026-09-28T16:56:02-04:00",
        },
        "resources2": {
            "units": [
                {
                    "unitId": {"name": "Engine 15"},
                    "personnel": [
                        {"agencyPerson": {"name": "Smith, John | 1516"}},
                    ],
                }
            ]
        },
        "cadNotes": "[16:56:30] 15-16 EN ROUTE POV",
    }

    scraper._parse_incident_dict(payload)

    # 1. Smith, John with badge 1516 should be auto-learned into scraper.members
    john = next((m for m in scraper.members if m.name == "Smith, John"), None)
    assert john is not None
    assert john.primary_id == "1516"
    assert "15-16" in john.aliases

    # 2. Because CADParser was refreshed with the auto-learned member, the CAD markup "15-16" was mapped to Smith, John!
    inc = scraper.intercepted_incidents["CO15202600999"]
    assert "Smith, John" in inc.radio_responders
    assert "15-16" in inc.radio_markups_found
    assert len(inc.unmapped_radio_marks) == 0




