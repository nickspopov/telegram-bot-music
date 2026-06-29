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
MUSIC_BOT_WORKDIR=/tmp/music-bot
```

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
