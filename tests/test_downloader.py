from music_bot.downloader import extract_youtube_url, is_youtube_url, safe_filename


def test_is_youtube_url_accepts_expected_hosts():
    assert is_youtube_url("https://youtu.be/abc")
    assert is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert is_youtube_url("https://music.youtube.com/watch?v=abc")


def test_is_youtube_url_rejects_lookalikes():
    assert not is_youtube_url("https://notyoutube.com/watch?v=abc")
    assert not is_youtube_url("https://youtube.com.evil.test/watch?v=abc")


def test_extract_youtube_url_from_text():
    assert extract_youtube_url("listen https://youtu.be/abc?si=1 thanks") == "https://youtu.be/abc?si=1"


def test_safe_filename_keeps_unicode_and_removes_fat_unsafe_chars():
    assert safe_filename('Вверх/вниз: track? * "x"') == "Вверх_вниз_ track_ _ _x"


def test_safe_filename_uses_fallback():
    assert safe_filename(' /:*?"<>| ') == "audio"
