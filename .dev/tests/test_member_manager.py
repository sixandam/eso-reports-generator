"""
Unit tests for member management, loading, saving, CSV import and export.
"""

from pathlib import Path
from eso_reports.models import Member
from eso_reports.member_manager import (
    load_members,
    save_members,
    export_members_to_csv,
    import_members_from_csv,
    get_active_roster_names,
)


def test_member_manager_seed_default(tmp_path: Path):
    target = tmp_path / "members.json"
    assert not target.exists()

    members = load_members(target)
    assert target.exists()
    assert len(members) >= 3
    # Charles Wellons should be present with CHF 15 alias
    wellons = next((m for m in members if "Wellons" in m.name), None)
    assert wellons is not None
    assert "CHF 15" in wellons.aliases
    assert wellons.active is True


def test_member_manager_save_and_load(tmp_path: Path):
    target = tmp_path / "members.json"
    members = [
        Member(
            name="Tester, First",
            primary_id="1599",
            aliases=["1599", "15-99", "T-15"],
            active=True,
        ),
        Member(
            name="Retired, Chief",
            primary_id="1500",
            aliases=["1500"],
            active=False,
        ),
    ]

    save_members(members, target)
    loaded = load_members(target)
    assert len(loaded) == 2
    assert loaded[0].name == "Tester, First"
    assert loaded[0].primary_id == "1599"
    assert loaded[0].aliases == ["1599", "15-99", "T-15"]
    assert loaded[0].active is True
    assert loaded[1].name == "Retired, Chief"
    assert loaded[1].active is False


def test_member_manager_csv_export_import(tmp_path: Path):
    csv_file = tmp_path / "members.csv"
    members = [
        Member(
            name="Smith, John",
            primary_id="1516",
            aliases=["1516", "15-16", "MEDIC 15"],
            active=True,
        ),
        Member(
            name="Doe, Jane",
            primary_id="1526",
            aliases=["1526"],
            active=False,
        ),
    ]

    export_members_to_csv(members, csv_file)
    assert csv_file.exists()

    imported = import_members_from_csv(csv_file)
    assert len(imported) == 2
    assert imported[0].name == "Smith, John"
    assert imported[0].primary_id == "1516"
    assert "MEDIC 15" in imported[0].aliases
    assert imported[0].active is True
    assert imported[1].name == "Doe, Jane"
    assert imported[1].active is False


def test_get_active_roster_names():
    members = [
        Member(name="Active, Member A", primary_id="1501", active=True),
        Member(name="Active, Member B", primary_id="1502", active=True),
        Member(name="Inactive, Member C", primary_id="1503", active=False),
    ]
    roster = get_active_roster_names(members)
    assert roster == ["Active, Member A", "Active, Member B"]


def test_auto_learn_member_badge():
    from eso_reports.member_manager import auto_learn_member_badge
    from eso_reports.models import extract_name_and_badge

    norm_name, badge = extract_name_and_badge("Glass, Lucas | 1545")
    assert norm_name == "Glass, Lucas"
    assert badge == "1545"

    members = [Member(name="Wellons, Charles", primary_id="1534", aliases=["1534"], active=True)]

    # 1. Learn brand new member from payload
    modified = auto_learn_member_badge(members, norm_name, badge)
    assert modified is True
    assert len(members) == 2

    lucas = next(m for m in members if m.name == "Glass, Lucas")
    assert lucas.primary_id == "1545"
    assert "1545" in lucas.aliases
    assert "15-45" in lucas.aliases
    assert lucas.active is True

    # 2. Re-learning same badge should not modify
    assert auto_learn_member_badge(members, norm_name, badge) is False

    # 3. Learning badge for existing member without primary_id
    members.append(Member(name="New, Firefighter", primary_id="", aliases=[], active=True))
    modified = auto_learn_member_badge(members, "New, Firefighter", "1598")
    assert modified is True
    ff = next(m for m in members if m.name == "New, Firefighter")
    assert ff.primary_id == "1598"
    assert "1598" in ff.aliases
    assert "15-98" in ff.aliases

