import os

import pytest

from music_bot.config import ConfigError, Settings, parse_allowed_user_ids


def test_parse_allowed_user_ids_accepts_commas_and_semicolons():
    assert parse_allowed_user_ids("123456789, 987654321;42") == {123456789, 987654321, 42}


def test_parse_allowed_user_ids_rejects_empty():
    with pytest.raises(ConfigError):
        parse_allowed_user_ids(" , ")


def test_settings_from_env_defaults(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ALLOWED_TELEGRAM_USER_IDS", raising=False)
    monkeypatch.delenv("OUTPUT_FORMAT", raising=False)
    settings = Settings.from_env(require_token=False)
    assert settings.allowed_user_ids == {123456789, 987654321}
    assert settings.output_format == "mp3"


def test_settings_requires_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(ConfigError):
        Settings.from_env(require_token=True)
