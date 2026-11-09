"""
Unit tests for CAD notes parsing, dispatcher notation variations,
typo correction, and unmapped radio marks detection.
"""

import pytest
from eso_reports.models import Member
from eso_reports.cad_parser import (
    CADParser,
    levenshtein_distance,
    normalize_numeric_token,
    normalize_command_token,
)


@pytest.fixture
def sample_members():
    return [
        Member(
            name="Wellons, Charles",
            primary_id="1534",
            aliases=["CHF 15", "CF15", "CHIEF 15", "1501", "15-01", "1534", "15-34"],
            active=True,
        ),
        Member(
            name="Glass, Lucas",
            primary_id="1545",
            aliases=["1545", "15-45"],
            active=True,
        ),
        Member(
            name="Glass, Ryne",
            primary_id="1530",
            aliases=["1530", "15-30"],
            active=True,
        ),
        Member(
            name="Garber, James Steven, Jr.",
            primary_id="1539",
            aliases=["1539", "15-39", "CAPT 15"],
            active=True,
        ),
        Member(
            name="Smith, Inactive",
            primary_id="1590",
            aliases=["1590"],
            active=False,
        ),
    ]


def test_levenshtein():
    assert levenshtein_distance("CHIEF", "CHIEF") == 0
    assert levenshtein_distance("CHEIF", "CHIEF") == 1
    assert levenshtein_distance("CHEF", "CHIEF") == 1
    assert levenshtein_distance("ABC", "DEF") == 3


def test_normalize_numeric_token():
    assert normalize_numeric_token("15O6") == "1506"
    assert normalize_numeric_token("l516") == "1516"
    assert normalize_numeric_token("I516") == "1516"
    assert normalize_numeric_token("1S16") == "1516"
    assert normalize_numeric_token("15 - 45") == "15-45"
    assert normalize_numeric_token("#1545") == "1545"
    assert normalize_numeric_token("M1545") == "1545"


def test_normalize_command_token():
    assert normalize_command_token("CHEIF 15") == "CHIEF 15"
    assert normalize_command_token("CHF   15") == "CHF 15"
    assert normalize_command_token("CHF15") == "CHF 15"


def test_exact_alias_matching(sample_members):
    parser = CADParser(sample_members)
    assert parser.match_token_to_member("1534").name == "Wellons, Charles"
    assert parser.match_token_to_member("CHF 15").name == "Wellons, Charles"
    assert parser.match_token_to_member("15-45").name == "Glass, Lucas"


def test_normalized_matching(sample_members):
    parser = CADParser(sample_members)
    # Hyphen variations
    assert parser.match_token_to_member("1545").name == "Glass, Lucas"
    # OCR typo: 'O' instead of '0' for 1530
    assert parser.match_token_to_member("153O").name == "Glass, Ryne"
    # Spaced hyphen
    assert parser.match_token_to_member("15 - 30").name == "Glass, Ryne"


def test_fuzzy_command_matching(sample_members):
    parser = CADParser(sample_members)
    # Misspelled command: CHEIF 15 -> CHIEF 15
    assert parser.match_token_to_member("CHEIF 15").name == "Wellons, Charles"
    # CE15 -> CF 15
    assert parser.match_token_to_member("CF 15").name == "Wellons, Charles"


def test_short_numeric_alias_does_not_match_times_or_addresses():
    parser = CADParser([Member(name="Wellons, Charles", primary_id="1534", aliases=["1534", "34"], active=True)])
    tokens, responders, unmapped = parser.parse_cad_text("CALL AT 17:34:05\n34 MAIN ST", incident_number="X")
    assert tokens == []
    assert responders == []
    assert unmapped == []


def test_cad_parsing_and_unmapped(sample_members):
    parser = CADParser(sample_members)
    cad_text = """
    [20:25:01] DISPATCH: 111 Building Fire on Main St.
    [20:26:10] 1545 EN ROUTE POV
    [20:26:30] 15-30, CHEIF 15 RESPONDING STATION
    [20:27:00] 1599 MARKED UP POV
    [20:28:15] 1590 EN ROUTE
    """
    tokens, responders, unmapped = parser.parse_cad_text(
        cad_text,
        incident_number="CO15202600443",
        incident_date="10/17/2026 20:25",
    )

    # Responders should include Glass, Lucas (1545), Glass, Ryne (15-30), and Wellons, Charles (CHEIF 15)
    assert "Glass, Lucas" in responders
    assert "Glass, Ryne" in responders
    assert "Wellons, Charles" in responders

    # Inactive member Smith (1590) should NOT be in active responders
    assert "Smith, Inactive" not in responders

    # 1599 is not in the roster, should be flagged as unmapped
    assert len(unmapped) == 1
    assert unmapped[0].token == "1599"
    assert unmapped[0].incident_number == "CO15202600443"
    assert "1599" in unmapped[0].snippet
    assert "No active member" in unmapped[0].reason


def test_bare_company_number_never_maps_but_full_forms_do():
    from eso_reports.cad_parser import CADParser, extract_unit_from_token
    from eso_reports.models import Member

    members = [Member(name="Salmons, Shaun", primary_id="1515", aliases=["1515", "15-15", "15"], active=True)]
    parser = CADParser(members)

    assert extract_unit_from_token("15") is None
    for form in ("1515", "15-15", "15 15"):
        assert extract_unit_from_token(form) == "1515"
        assert parser.match_token_to_member(form) is members[0]
    assert parser.match_token_to_member("15") is None

    _, responders, _ = parser.parse_cad_text("11/5/2026 10:59:12 - Company 15 disregarded", "X")
    assert responders == []
    _, responders, _ = parser.parse_cad_text("11/5/2026 11:01:00 - 15 15 ENRT", "X")
    assert responders == ["Salmons, Shaun"]


def test_short_numeric_aliases_do_not_match_ordinary_numbers():
    from eso_reports.cad_parser import CADParser
    from eso_reports.models import Member

    members = [Member(name="Watson, Mike", primary_id="1510", aliases=["1510", "15-10", "10"], active=True)]
    parser = CADParser(members)
    tokens, responders, _ = parser.parse_cad_text("11/6/2026 09:00:00 - copy 10/4 on 10/15/2026", "X")
    assert responders == []
    _, responders, _ = parser.parse_cad_text("11/6/2026 09:01:00 - 1510 ENRT", "X")
    assert responders == ["Watson, Mike"]
