"""
Tests for data models and aggregator metrics logic.
"""

import pytest
from eso_reports.models import Incident, normalize_personnel_name
from eso_reports.aggregator import build_report_dataset


def test_normalize_personnel_name():
    assert normalize_personnel_name("Adams, John") == "Adams, John"
    assert normalize_personnel_name("John Adams") == "Adams, John"
    assert normalize_personnel_name("ADAMS, J.") == "Adams, J."
    assert normalize_personnel_name("Adams, J") == "Adams, J."
    assert normalize_personnel_name("  baker,  mike  ") == "Baker, Mike"
    assert normalize_personnel_name("Clark, R. ") == "Clark, R."
    assert normalize_personnel_name("") == ""
    assert normalize_personnel_name("Smith, John, III") == "Smith, John, III"
    assert normalize_personnel_name("Smith, John III") == "Smith, John, III"
    assert normalize_personnel_name("Smith, John IV") == "Smith, John, IV"
    assert normalize_personnel_name("John Smith, Jr.") == "Smith, John, Jr."
    assert normalize_personnel_name("John Smith Jr") == "Smith, John, Jr."
    assert normalize_personnel_name("Garber, James Steven, JR | 1539") == "Garber, James Steven, Jr."


def test_normalize_apparatus_name():
    from eso_reports.aggregator import normalize_apparatus_name
    assert normalize_apparatus_name("engine 15") == "Engine 15"
    assert normalize_apparatus_name("ENGINE 15") == "Engine 15"
    assert normalize_apparatus_name("pov") == "POV"
    assert normalize_apparatus_name("POV") == "POV"
    assert normalize_apparatus_name("station standby") == "Station Standby"
    assert normalize_apparatus_name("rescue 15") == "Rescue 15"


def test_build_report_dataset_basic():
    incidents = [
        Incident(
            incident_number="24-00101",
            incident_type="111 - Building fire",
            responders=["Adams, J.", "Baker, M."],
        ),
        Incident(
            incident_number="24-00102",
            incident_type="321 - EMS call",
            responders=["Adams, J.", "Clark, R."],
        ),
        Incident(
            incident_number="24-00103",
            incident_type="321 - EMS call",
            responders=["Baker, M.", "Davis, S."],
        ),
        Incident(
            incident_number="24-00104",
            incident_type="111 - Building fire",
            responders=["Adams, J.", "Baker, M.", "Clark, R.", "Davis, S."],
        ),
    ]

    dataset = build_report_dataset(incidents)

    # Total incidents
    assert dataset.total_incidents == 4

    # Roster should be alphabetically sorted
    assert dataset.roster == ["Adams, J.", "Baker, M.", "Clark, R.", "Davis, S."]

    # Personnel summaries
    # Adams, J: 3/4 calls (75.0%)
    adams = dataset.personnel_summaries["Adams, J."]
    assert adams.calls_made == 3
    assert adams.percentage == 75.0
    assert adams.formatted_ratio == "3/4 (75.0%)"

    # Baker, M: 3/4 calls (75.0%)
    baker = dataset.personnel_summaries["Baker, M."]
    assert baker.calls_made == 3
    assert baker.formatted_ratio == "3/4 (75.0%)"

    # Clark, R: 2/4 calls (50.0%)
    clark = dataset.personnel_summaries["Clark, R."]
    assert clark.calls_made == 2
    assert clark.formatted_ratio == "2/4 (50.0%)"

    # Davis, S: 2/4 calls (50.0%)
    davis = dataset.personnel_summaries["Davis, S."]
    assert davis.calls_made == 2
    assert davis.formatted_ratio == "2/4 (50.0%)"

    # Attendance Matrix checks
    assert dataset.attendance_matrix["24-00101"]["Adams, J."] is True
    assert dataset.attendance_matrix["24-00101"]["Baker, M."] is True
    assert dataset.attendance_matrix["24-00101"]["Clark, R."] is False

    # Incident Types: 2 Building fire, 2 EMS call
    assert len(dataset.type_summaries) == 2
    types_dict = {t.incident_type: t for t in dataset.type_summaries}
    assert "111 - Building fire" in types_dict
    assert types_dict["111 - Building fire"].count == 2
    assert types_dict["111 - Building fire"].percentage == 50.0
    assert types_dict["111 - Building fire"].formatted_summary == "111 - Building fire: 2/4 (50.0%)"

    assert types_dict["321 - EMS call"].count == 2
    assert types_dict["321 - EMS call"].percentage == 50.0
    assert types_dict["321 - EMS call"].formatted_summary == "321 - EMS call: 2/4 (50.0%)"


def test_build_report_dataset_with_roster_zero_calls():
    # Test when a department member on roster attended 0 calls
    incidents = [
        Incident(
            incident_number="24-00001",
            incident_type="111 - Building fire",
            responders=["Active, A."],
        )
    ]
    known_roster = ["Active, A.", "Inactive, I."]

    dataset = build_report_dataset(incidents, known_roster=known_roster)

    assert dataset.total_incidents == 1
    assert dataset.roster == ["Active, A.", "Inactive, I."]

    inactive = dataset.personnel_summaries["Inactive, I."]
    assert inactive.calls_made == 0
    assert inactive.percentage == 0.0
    assert inactive.formatted_ratio == "0/1 (0.0%)"


def test_build_report_dataset_empty():
    dataset = build_report_dataset([])
    assert dataset.total_incidents == 0
    assert dataset.roster == []
    assert len(dataset.type_summaries) == 0
    assert len(dataset.apparatus_summaries) == 0


def test_build_report_dataset_apparatus():
    incidents = [
        Incident(
            incident_number="24-00201",
            incident_type="111 - Building fire",
            responders=["Adams, J."],
            apparatus=["Engine 15", "POV"],
        ),
        Incident(
            incident_number="24-00202",
            incident_type="321 - EMS call",
            responders=["Baker, M."],
            apparatus=["Engine 15"],
        ),
        Incident(
            incident_number="24-00203",
            incident_type="321 - EMS call",
            responders=["Clark, R."],
            apparatus=["Station Standby"],
        ),
    ]

    dataset = build_report_dataset(incidents)
    assert len(dataset.apparatus_summaries) == 3

    app_dict = {a.apparatus_name: a for a in dataset.apparatus_summaries}
    assert "Engine 15" in app_dict
    assert app_dict["Engine 15"].count == 2
    assert pytest.approx(app_dict["Engine 15"].percentage, 0.1) == 66.7
    assert app_dict["Engine 15"].formatted_summary == "Engine 15: 2/3 (66.7%)"

    assert "POV" in app_dict
    assert app_dict["POV"].count == 1
    assert app_dict["POV"].formatted_summary == "POV: 1/3 (33.3%)"

    assert "Station Standby" in app_dict
    assert app_dict["Station Standby"].count == 1
    assert app_dict["Station Standby"].formatted_summary == "Station Standby: 1/3 (33.3%)"


def test_build_report_dataset_inactive_segregation():
    incidents = [
        Incident(
            incident_number="CO15202600407",
            incident_type="Gas leak / gas odor",
            responders=["Adams, John"],
            status="ACTIVE",
        ),
        Incident(
            incident_number="260905-134412-LDHVFD",
            incident_type="Unknown Incident Type",
            responders=[],
            status="INACTIVE",
        ),
    ]

    dataset = build_report_dataset(incidents)
    assert dataset.total_incidents == 1
    assert len(dataset.incidents) == 1
    assert dataset.incidents[0].incident_number == "CO15202600407"
    assert len(dataset.inactive_incidents) == 1
    assert dataset.inactive_incidents[0].incident_number == "260905-134412-LDHVFD"
    assert dataset.personnel_summaries["Adams, John"].calls_made == 1
    assert dataset.personnel_summaries["Adams, John"].total_incidents == 1
    assert dataset.personnel_summaries["Adams, John"].percentage == 100.0


def test_incident_model_extra_fields_ignored():
    # Verify that unknown/future ESO RMS fields are safely ignored by Pydantic models
    inc = Incident(
        incident_number="CO15202600407",
        incident_type="Gas leak",
        future_neris_field="test_value",
        unknown_metadata={"code": 123},
    )
    assert inc.incident_number == "CO15202600407"
    assert not hasattr(inc, "future_neris_field")


