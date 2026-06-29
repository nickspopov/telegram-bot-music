import base64

import pytest

from music_bot.config import Settings
from music_bot.downloader import ProcessingError, _build_ydl_opts, extract_youtube_url, is_youtube_url, safe_filename


def test_is_youtube_url_accepts_expected_hosts():
    video_id = "dQw4w9WgXcQ"
    assert is_youtube_url(f"https://youtu.be/{video_id}")
    assert is_youtube_url(f"https://www.youtube.com/watch?v={video_id}")
    assert is_youtube_url(f"https://music.youtube.com/watch?v={video_id}")
    assert is_youtube_url(f"https://www.youtube.com/shorts/{video_id}")


def test_is_youtube_url_rejects_lookalikes():
    assert not is_youtube_url("https://notyoutube.com/watch?v=abc")
    assert not is_youtube_url("https://youtube.com.evil.test/watch?v=abc")


def test_is_youtube_url_rejects_non_video_urls():
    assert not is_youtube_url("http://youtube.com/watch?v=dQw4w9WgXcQ")
    assert not is_youtube_url("https://www.youtube.com/playlist?list=PL123456789")
    assert not is_youtube_url("https://www.youtube.com/@somechannel")
    assert not is_youtube_url("https://www.youtube.com/results?search_query=test")


def test_extract_youtube_url_from_text():
    assert extract_youtube_url("listen https://youtu.be/dQw4w9WgXcQ?si=1 thanks") == "https://youtu.be/dQw4w9WgXcQ?si=1"


def test_safe_filename_keeps_unicode_and_removes_fat_unsafe_chars():
    assert safe_filename('Вверх/вниз: track? * "x"') == "Вверх_вниз_ track_ _ _x"


def test_safe_filename_uses_fallback():
    assert safe_filename(' /:*?"<>| ') == "audio"


def test_build_ydl_opts_decodes_b64_cookies_and_proxy(monkeypatch, tmp_path):
    cookies = b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\ttest\n"
    monkeypatch.setenv("YTDLP_COOKIES_B64", base64.b64encode(cookies).decode())
    monkeypatch.setenv("YTDLP_PROXY", "socks5://127.0.0.1:9050")
    settings = Settings.from_env(require_token=False)

    opts = _build_ydl_opts(settings, tmp_path)

    assert opts["proxy"] == "socks5://127.0.0.1:9050"
    cookiefile = tmp_path / "youtube-cookies.txt"
    assert opts["cookiefile"] == str(cookiefile)
    assert cookiefile.read_bytes() == cookies


def test_build_ydl_opts_rejects_invalid_b64_cookies(monkeypatch, tmp_path):
    monkeypatch.setenv("YTDLP_COOKIES_B64", "not-base64!!!")
    settings = Settings.from_env(require_token=False)

    with pytest.raises(ProcessingError, match="not valid base64"):
        _build_ydl_opts(settings, tmp_path)
