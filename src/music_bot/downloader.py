import base64
import binascii
import json
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urlparse

import yt_dlp

from .config import Settings

LOGGER = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
FAT_UNSAFE_CHARS_RE = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")
WHITESPACE_RE = re.compile(r"\s+")
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,}$")
YOUTUBE_HOSTS = {"youtube.com", "youtu.be", "youtube-nocookie.com"}
MP4_SUFFIXES = {".m4a", ".mp4", ".m4b", ".mov"}


class ProcessingError(RuntimeError):
    pass


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    codec: str
    sample_rate: Optional[int]
    channels: Optional[int]
    major_brand: str
    message: str


@dataclass(frozen=True)
class AudioArtifact:
    path: Path
    filename: str
    title: str
    performer: str
    duration: Optional[int]
    validation: ValidationResult


def _valid_video_id(value: Optional[str]) -> bool:
    return bool(value and VIDEO_ID_RE.match(value))


def is_youtube_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
        return _valid_video_id(video_id)

    if not (host in YOUTUBE_HOSTS or host.endswith(".youtube.com") or host.endswith(".youtube-nocookie.com")):
        return False

    path_parts = [part for part in parsed.path.split("/") if part]
    if parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        return _valid_video_id(video_id)

    if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
        return _valid_video_id(path_parts[1])

    return False


def extract_youtube_url(text: str) -> Optional[str]:
    for match in URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,;)]}>")
        if is_youtube_url(url):
            return url
    return None


def safe_filename(name: str, fallback: str = "audio", max_len: int = 120) -> str:
    cleaned = FAT_UNSAFE_CHARS_RE.sub("_", name or "")
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip(" ._")
    if not cleaned:
        cleaned = fallback
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip(" ._")
    return cleaned or fallback


def ensure_tools_available() -> None:
    missing = [cmd for cmd in ("ffmpeg", "ffprobe") if shutil.which(cmd) is None]
    if missing:
        raise ProcessingError("Missing required command(s): " + ", ".join(missing))


def run_cmd(args: List[str], timeout: int = 600) -> subprocess.CompletedProcess:
    LOGGER.debug("Running command: %s", " ".join(args[:2] + ["..."] if len(args) > 2 else args))
    return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)


def _ffprobe_json(path: Path) -> Dict[str, Any]:
    proc = run_cmd([
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ])
    if proc.returncode != 0:
        raise ProcessingError(f"ffprobe failed: {proc.stderr.strip() or proc.stdout.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ProcessingError("ffprobe returned invalid JSON") from exc


def _has_fragment_boxes(path: Path) -> bool:
    if path.suffix.lower() not in MP4_SUFFIXES:
        return False
    proc = run_cmd(["ffprobe", "-v", "trace", str(path)], timeout=120)
    trace = f"{proc.stdout}\n{proc.stderr}"
    return "type:'moof'" in trace or "type:'sidx'" in trace


def _first_audio_stream(probe: Dict[str, Any]) -> Dict[str, Any]:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "audio":
            return stream
    raise ProcessingError("No audio stream found in output")


def validate_audio_file(path: Path) -> ValidationResult:
    if not path.exists() or path.stat().st_size <= 0:
        raise ProcessingError("Output file is missing or empty")

    probe = _ffprobe_json(path)
    audio = _first_audio_stream(probe)
    fmt = probe.get("format", {})
    tags = fmt.get("tags", {}) or {}

    codec = str(audio.get("codec_name") or "").lower()
    profile = str(audio.get("profile") or "")
    sample_rate_raw = audio.get("sample_rate")
    sample_rate = int(sample_rate_raw) if str(sample_rate_raw or "").isdigit() else None
    channels = audio.get("channels") if isinstance(audio.get("channels"), int) else None
    major_brand = str(tags.get("major_brand") or "")

    if codec == "mp3":
        if sample_rate not in {44100, 48000}:
            raise ProcessingError(f"MP3 sample rate {sample_rate} is outside safe 44.1/48 kHz profile")
        if channels not in {1, 2}:
            raise ProcessingError(f"MP3 channel count {channels} is unsupported")
        return ValidationResult(True, codec, sample_rate, channels, major_brand, "OK: MP3 safe profile")

    if codec == "aac":
        if major_brand == "dash":
            raise ProcessingError("REJECT: major_brand=dash")
        if _has_fragment_boxes(path):
            raise ProcessingError("REJECT: fragmented MP4 container has moof/sidx boxes")
        if profile and profile != "LC":
            raise ProcessingError(f"REJECT: AAC profile={profile!r}, want LC")
        return ValidationResult(True, codec, sample_rate, channels, major_brand, "OK: AAC-LC non-fragmented profile")

    raise ProcessingError(f"REJECT: unsupported codec {codec!r}")


def _metadata_args(info: Dict[str, Any]) -> List[str]:
    args: List[str] = []
    title = info.get("title")
    artist = info.get("artist") or info.get("creator") or info.get("uploader")
    if title:
        args.extend(["-metadata", f"title={title}"])
    if artist:
        args.extend(["-metadata", f"artist={artist}"])
    return args


def _pick_downloaded_file(directory: Path, ignored: Iterable[Path]) -> Path:
    ignored_set = {p.resolve() for p in ignored}
    candidates = [
        p
        for p in directory.iterdir()
        if p.is_file() and p.resolve() not in ignored_set and not p.name.endswith((".part", ".ytdl"))
    ]
    if not candidates:
        raise ProcessingError("yt-dlp did not produce an input file")
    return max(candidates, key=lambda p: p.stat().st_size)


def _cookies_file_from_settings(settings: Settings, tmp: Path) -> Optional[Path]:
    if settings.ytdlp_cookies_file:
        if not settings.ytdlp_cookies_file.exists():
            raise ProcessingError(f"YTDLP_COOKIES_FILE does not exist: {settings.ytdlp_cookies_file}")
        return settings.ytdlp_cookies_file

    if not settings.ytdlp_cookies_b64:
        return None

    try:
        cookie_bytes = base64.b64decode(settings.ytdlp_cookies_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProcessingError("YTDLP_COOKIES_B64 is not valid base64") from exc

    if not cookie_bytes.startswith((b"# Netscape HTTP Cookie File", b"# HTTP Cookie File")):
        raise ProcessingError("YTDLP_COOKIES_B64 must decode to a Netscape cookies.txt file")

    cookies_path = tmp / "youtube-cookies.txt"
    cookies_path.write_bytes(cookie_bytes)
    cookies_path.chmod(0o600)
    return cookies_path


def _build_ydl_opts(settings: Settings, tmp: Path) -> Dict[str, Any]:
    ydl_opts: Dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": str(tmp / "source.%(ext)s"),
        "extractor_args": {
            "youtube": {
                "player_client": ["web_embedded", "mweb"],
            },
        },
        "noplaylist": True,
        "max_filesize": settings.max_source_bytes,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "cachedir": False,
    }
    cookies_file = _cookies_file_from_settings(settings, tmp)
    if cookies_file:
        ydl_opts["cookiefile"] = str(cookies_file)
    if settings.ytdlp_proxy:
        ydl_opts["proxy"] = settings.ytdlp_proxy
    return ydl_opts


def process_youtube_url(url: str, output_dir: Path, settings: Settings) -> AudioArtifact:
    if not is_youtube_url(url):
        raise ProcessingError("Only YouTube links are supported")

    ensure_tools_available()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="yt-", dir=str(output_dir)) as tmp_raw:
        tmp = Path(tmp_raw)
        ydl_opts = _build_ydl_opts(settings, tmp)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not isinstance(info, dict):
                    raise ProcessingError("yt-dlp returned no video metadata")
                live_status = info.get("live_status")
                if info.get("is_live") or live_status in {"is_live", "is_upcoming", "post_live"}:
                    raise ProcessingError("Live/upcoming streams are not supported")
                duration = info.get("duration")
                if not isinstance(duration, (int, float)):
                    raise ProcessingError("Could not determine video duration")
                if isinstance(duration, (int, float)) and duration > settings.max_duration_seconds:
                    raise ProcessingError(
                        f"Video is too long ({int(duration)}s > {settings.max_duration_seconds}s limit)"
                    )
                info = ydl.extract_info(url, download=True)
        except yt_dlp.utils.DownloadError as exc:
            raise ProcessingError(f"yt-dlp failed: {exc}") from exc

        if not isinstance(info, dict):
            raise ProcessingError("yt-dlp returned no video metadata")

        source = _pick_downloaded_file(tmp, ignored=[])
        title = str(info.get("title") or "YouTube audio")
        performer = str(info.get("artist") or info.get("creator") or info.get("uploader") or "")
        filename_base = safe_filename(title)
        output_path = output_dir / f"{filename_base}.mp3"

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-vn",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "320k",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-id3v2_version",
            "3",
            *_metadata_args(info),
            str(output_path),
        ]
        proc = run_cmd(ffmpeg_cmd, timeout=900)
        if proc.returncode != 0:
            raise ProcessingError(f"ffmpeg failed: {proc.stderr.strip() or proc.stdout.strip()}")

    if output_path.stat().st_size > settings.max_output_bytes:
        output_path.unlink(missing_ok=True)
        raise ProcessingError(
            f"Converted file is too large for Telegram upload ({settings.max_output_bytes} byte limit)"
        )

    validation = validate_audio_file(output_path)
    return AudioArtifact(
        path=output_path,
        filename=output_path.name,
        title=title,
        performer=performer,
        duration=int(info["duration"]) if isinstance(info.get("duration"), (int, float)) else None,
        validation=validation,
    )
