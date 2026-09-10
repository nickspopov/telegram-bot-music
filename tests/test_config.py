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
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "123456789,987654321")
    monkeypatch.delenv("OUTPUT_FORMAT", raising=False)
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)
    monkeypatch.delenv("YTDLP_COOKIES_B64", raising=False)
    monkeypatch.delenv("YTDLP_PROXY", raising=False)
    settings = Settings.from_env(require_token=False)
    assert settings.allowed_user_ids == {123456789, 987654321}
    assert settings.output_format == "mp3"
    assert settings.max_source_bytes == 150 * 1024 * 1024
    assert settings.ytdlp_cookies_file is None
    assert settings.ytdlp_cookies_b64 == ""
    assert settings.ytdlp_proxy == ""


def test_settings_requires_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(ConfigError):
        Settings.from_env(require_token=True)


def test_settings_rejects_both_cookie_sources(monkeypatch):
    monkeypatch.setenv("YTDLP_COOKIES_FILE", "/tmp/cookies.txt")
    monkeypatch.setenv("YTDLP_COOKIES_B64", "abc")
    with pytest.raises(ConfigError, match="Set only one"):
        Settings.from_env(require_token=False)
