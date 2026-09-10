"""Configuration parsing.

Every setting the README documents must actually work when set that way -- a
setting that crashes on startup is worse than one that does not exist.
"""

import pytest

from app.config import Settings


def test_cors_origins_accepts_a_comma_separated_list(monkeypatch: pytest.MonkeyPatch):
    """pydantic-settings parses list fields as JSON by default, so the obvious
    comma-separated form raised SettingsError and the service refused to boot."""
    monkeypatch.setenv("AUTOCHECK_CORS_ORIGINS", "http://a.test,http://b.test")

    assert Settings().cors_origins == ["http://a.test", "http://b.test"]


def test_cors_origins_tolerates_spaces_around_entries(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTOCHECK_CORS_ORIGINS", "http://a.test , http://b.test")

    assert Settings().cors_origins == ["http://a.test", "http://b.test"]


def test_cors_origins_still_accepts_json(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTOCHECK_CORS_ORIGINS", '["http://a.test"]')

    assert Settings().cors_origins == ["http://a.test"]


def test_a_single_origin_needs_no_list_syntax(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTOCHECK_CORS_ORIGINS", "http://a.test")

    assert Settings().cors_origins == ["http://a.test"]


def test_interval_of_zero_is_allowed_to_disable_the_scheduler(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTOCHECK_INGEST_INTERVAL_SECONDS", "0")

    assert Settings().ingest_interval_seconds == 0


def test_feed_dir_and_database_url_are_overridable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTOCHECK_FEED_DIR", "/tmp/somewhere")
    monkeypatch.setenv("AUTOCHECK_DATABASE_URL", "sqlite:////tmp/x.db")

    settings = Settings()
    assert str(settings.feed_dir) == "/tmp/somewhere"
    assert settings.database_url == "sqlite:////tmp/x.db"
