import argparse
import shutil
import sys

import telegram
import yt_dlp

from . import __version__
from .config import ConfigError, Settings
from .downloader import ensure_tools_available
from .bot import run_bot


def check_env(require_token: bool = True) -> int:
    try:
        settings = Settings.from_env(require_token=require_token)
        ensure_tools_available()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"music_bot={__version__}")
    print(f"python-telegram-bot={telegram.__version__}")
    print(f"yt-dlp={yt_dlp.version.__version__}")
    print(f"ffmpeg={shutil.which('ffmpeg')}")
    print(f"ffprobe={shutil.which('ffprobe')}")
    print(f"allowed_user_ids={','.join(str(i) for i in sorted(settings.allowed_user_ids))}")
    print(f"max_source_bytes={settings.max_source_bytes}")
    print(f"token_configured={bool(settings.bot_token)}")
    print("OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Telegram YouTube-to-audio bot")
    parser.add_argument("--check-env", action="store_true", help="verify runtime dependencies without starting Telegram")
    parser.add_argument(
        "--no-token-required",
        action="store_true",
        help="allow --check-env to pass without TELEGRAM_BOT_TOKEN, useful for image smoke tests",
    )
    args = parser.parse_args()

    if args.check_env:
        return check_env(require_token=not args.no_token_required)

    try:
        settings = Settings.from_env(require_token=True)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    run_bot(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
