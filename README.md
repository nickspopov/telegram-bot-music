# telegram-bot-music

Telegram bot that accepts YouTube links from an allowlist, downloads best available audio, converts it to a HIFI WALKER H2 Mini-safe file, validates the result with `ffprobe`, and uploads the audio back to the chat.

## Behavior

- Only these Telegram user IDs are allowed by default: `123456789`, `987654321`.
- Unauthorized users are ignored silently.
- Uses long polling, so no public HTTP port or webhook is required.
- Default output is **MP3 320 kbps CBR, 44.1 kHz, stereo** — the safest profile from `HIFI_WALKER_H2_file_spec.md`.
- Rejects over-long videos and files above the configured Telegram upload limit.
- Never commits or bakes the bot token into the image; set it as an environment variable.

## Environment

```env
TELEGRAM_BOT_TOKEN=...
ALLOWED_TELEGRAM_USER_IDS=123456789,987654321
OUTPUT_FORMAT=mp3
MAX_DURATION_SECONDS=1800
MAX_OUTPUT_BYTES=52428800
MAX_SOURCE_BYTES=157286400
YTDLP_COOKIES_B64=
YTDLP_COOKIES_FILE=
YTDLP_PROXY=
MUSIC_BOT_WORKDIR=/tmp/music-bot
```

## YouTube bot-check / cookies

YouTube often blocks datacenter VPS IPs with `Sign in to confirm you’re not a bot` even when the same URL works from a home laptop. The bot supports two runtime-only workarounds:

- `YTDLP_COOKIES_B64`: base64-encoded Netscape `cookies.txt` file; recommended for Coolify env vars.
- `YTDLP_COOKIES_FILE`: path to a mounted Netscape `cookies.txt` file.
- `YTDLP_PROXY`: optional proxy URL passed to yt-dlp, useful if the VPS IP itself is flagged.

Export YouTube cookies from a private/incognito browser session and keep them secret. Do not commit them. Per yt-dlp guidance, a throwaway YouTube account is safer because cookies can be rate-limited or banned.

On macOS/Linux, after exporting `cookies.txt`:

```bash
base64 < cookies.txt | tr -d '\n'
```

Paste the output into Coolify as `YTDLP_COOKIES_B64`, then redeploy.

## Local run

```bash
cp .env.example .env
# edit TELEGRAM_BOT_TOKEN

docker compose up --build
```

## Coolify deployment

Use this repo as a Docker Compose application in Coolify.

Recommended settings:

- Source: `git@github.com:nickspopov/telegram-bot-music.git`
- Build pack / type: Docker Compose
- Compose file: `docker-compose.yml`
- No exposed port/domain needed; this is a Telegram long-polling worker.
- Runtime environment variables:
  - `TELEGRAM_BOT_TOKEN`
  - `ALLOWED_TELEGRAM_USER_IDS=123456789,987654321`
  - `YTDLP_COOKIES_B64` if YouTube blocks the VPS as a bot
  - optional limits from `.env.example`

## Validation logic

For the default MP3 profile the bot validates:

- one audio stream exists;
- codec is `mp3`;
- sample rate is 44.1 kHz;
- output size is non-zero and under `MAX_OUTPUT_BYTES`.

The validator also supports AAC/M4A checks from the H2 spec:

- reject `major_brand=dash`;
- reject `moof`/`sidx` fragmented containers;
- warn/reject non-LC AAC profiles.

## Tests

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```
