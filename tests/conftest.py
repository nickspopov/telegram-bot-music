import pytest


@pytest.fixture(autouse=True)
def allowlist_env(monkeypatch):
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "123456789,987654321")
