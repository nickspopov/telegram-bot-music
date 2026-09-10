import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Set


DEFAULT_MAX_DURATION_SECONDS = 30 * 60
DEFAULT_MAX_OUTPUT_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_SOURCE_BYTES = 150 * 1024 * 1024


class ConfigError(ValueError):
    pass


def parse_allowed_user_ids(raw: str) -> Set[int]:
    ids: Set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError as exc:
            raise ConfigError(f"Invalid Telegram user id: {part!r}") from exc
    if not ids:
        raise ConfigError("ALLOWED_TELEGRAM_USER_IDS must contain at least one user id")
    return ids


def _int_env(env: Dict[str, str], name: str, default: int) -> int:
    raw = env.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be positive")
    return value


@dataclass(frozen=True)
class Settings:
    bot_token: str
    allowed_user_ids: Set[int]
    output_format: str
    max_duration_seconds: int
    max_output_bytes: int
    max_source_bytes: int
    workdir: Path
    ytdlp_cookies_file: Optional[Path]
    ytdlp_cookies_b64: str
    ytdlp_proxy: str

    @classmethod
    def from_env(cls, require_token: bool = True) -> "Settings":
        env = dict(os.environ)
        token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
        if require_token and not token:
            raise ConfigError("TELEGRAM_BOT_TOKEN is required")

        output_format = env.get("OUTPUT_FORMAT", "mp3").strip().lower()
        if output_format != "mp3":
            raise ConfigError("Only OUTPUT_FORMAT=mp3 is currently supported")

        allowed_raw = env.get("ALLOWED_TELEGRAM_USER_IDS", "").strip()
        if not allowed_raw:
            raise ConfigError("ALLOWED_TELEGRAM_USER_IDS is required (comma-separated Telegram user ids)")
        allowed = parse_allowed_user_ids(allowed_raw)
        workdir = Path(env.get("MUSIC_BOT_WORKDIR", "/tmp/music-bot")).expanduser()
        ytdlp_cookies_file_raw = env.get("YTDLP_COOKIES_FILE", "").strip()
        ytdlp_cookies_b64 = env.get("YTDLP_COOKIES_B64", "").strip()
        if ytdlp_cookies_file_raw and ytdlp_cookies_b64:
            raise ConfigError("Set only one of YTDLP_COOKIES_FILE or YTDLP_COOKIES_B64")

        return cls(
            bot_token=token,
            allowed_user_ids=allowed,
            output_format=output_format,
            max_duration_seconds=_int_env(env, "MAX_DURATION_SECONDS", DEFAULT_MAX_DURATION_SECONDS),
            max_output_bytes=_int_env(env, "MAX_OUTPUT_BYTES", DEFAULT_MAX_OUTPUT_BYTES),
            max_source_bytes=_int_env(env, "MAX_SOURCE_BYTES", DEFAULT_MAX_SOURCE_BYTES),
            workdir=workdir,
            ytdlp_cookies_file=Path(ytdlp_cookies_file_raw).expanduser() if ytdlp_cookies_file_raw else None,
            ytdlp_cookies_b64=ytdlp_cookies_b64,
            ytdlp_proxy=env.get("YTDLP_PROXY", "").strip(),
        )
