"""Validate user-supplied YouTube media links before network access."""
import re
from urllib.parse import parse_qs, urlsplit

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")
PLAYLIST_ID = re.compile(r"[A-Za-z0-9_-]{2,150}\Z")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}


def validate_youtube_url(value: str) -> str:
    value = value.strip()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError("Provide a valid YouTube HTTP or HTTPS link") from None
    if (parsed.scheme not in ("http", "https") or parsed.username is not None
            or parsed.password is not None or port not in (None, 80 if parsed.scheme == "http" else 443)
            or any(character.isspace() or ord(character) < 32 for character in value) or "\\" in value):
        raise ValueError("Provide a valid YouTube HTTP or HTTPS link")
    host = parsed.hostname
    if host not in YOUTUBE_HOSTS | {"youtu.be", "www.youtu.be", "youtube-nocookie.com", "www.youtube-nocookie.com"}:
        raise ValueError("Only YouTube links are supported")
    path = parsed.path.rstrip("/")
    query = parse_qs(parsed.query, keep_blank_values=True)

    def single_id(name, pattern):
        values = query.get(name, [])
        return len(values) == 1 and pattern.fullmatch(values[0]) is not None

    if host in {"youtu.be", "www.youtu.be"}:
        valid = VIDEO_ID.fullmatch(path.removeprefix("/")) is not None
    elif host in {"youtube-nocookie.com", "www.youtube-nocookie.com"}:
        valid = re.fullmatch(r"/embed/[A-Za-z0-9_-]{11}", path) is not None
    elif path == "/watch":
        valid = single_id("v", VIDEO_ID)
    elif path == "/playlist":
        valid = single_id("list", PLAYLIST_ID)
    else:
        valid = re.fullmatch(r"/(shorts|live|embed)/[A-Za-z0-9_-]{11}", path) is not None
    if not valid:
        raise ValueError("Provide a valid YouTube video or playlist link")
    # A supplied playlist must also be well formed, even on a video link.
    if "list" in query and not single_id("list", PLAYLIST_ID):
        raise ValueError("Provide a valid YouTube playlist ID")
    return value
