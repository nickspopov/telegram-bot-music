FROM denoland/deno:bin-2.5.2 AS deno

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1

RUN apt-get update     && apt-get install -y --no-install-recommends ffmpeg ca-certificates     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=deno /deno /usr/local/bin/deno

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

RUN useradd --create-home --shell /usr/sbin/nologin appuser     && mkdir -p /tmp/music-bot     && chown -R appuser:appuser /app /tmp/music-bot

USER appuser
ENV PYTHONPATH=/app/src     MUSIC_BOT_WORKDIR=/tmp/music-bot

HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3     CMD python -m music_bot --check-env || exit 1

CMD ["python", "-m", "music_bot"]
