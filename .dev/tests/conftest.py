"""Shared fixtures: keeps every test away from the user's real application config."""

import pytest

from eso_reports import member_manager


@pytest.fixture(autouse=True)
def isolated_members_file(tmp_path, monkeypatch):
    """Redirects members.json to a temp directory so tests can never overwrite a real roster."""
    config_dir = tmp_path / "isolated-config"
    monkeypatch.setattr(member_manager, "APP_CONFIG_DIR", config_dir)
    monkeypatch.setattr(member_manager, "MEMBERS_FILE", config_dir / "members.json")
