"""Metadata-only extraction and best-effort public-network validation."""
import ipaddress
import math
import socket
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

if __package__:
    from .contracts import MediaFormat, PreviewItem, PreviewResponse, UrlRequest
    from .errors import ApiException
else:
    from contracts import MediaFormat, PreviewItem, PreviewResponse, UrlRequest
    from errors import ApiException


def validate_target(url: str) -> str:
    try:
        url = UrlRequest(url=url).url
        parsed = urlsplit(url)
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    except (ValueError, socket.gaierror):
        raise ApiException(422, 'invalid_target', 'The link must resolve to a public HTTP or HTTPS address.') from None
    if not addresses or any(not ipaddress.ip_address(address[4][0].split('%')[0]).is_global for address in addresses):
        raise ApiException(422, 'blocked_target', 'Local and private network links are not allowed.')
    return url


class QuietLogger:
    def debug(self, message):
        pass
    def warning(self, message):
        pass
    def error(self, message):
        pass


class PublicYoutubeDL(YoutubeDL):
    def urlopen(self, request):
        # Checks extractor-generated requests too. Transport redirects and DNS
        # rebinding still require deployment-level egress restrictions.
        validate_target(request if isinstance(request, str) else request.url)
        return super().urlopen(request)


@contextmanager
def cookie_options(cookie_file):
    """yt-dlp writes its jar on exit; never modify the protected host file."""
    if cookie_file is None:
        yield {}
        return
    path = Path(cookie_file)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o007:
        raise ApiException(422, 'cookie_file_unavailable', 'The server cookie file is unavailable.')
    with tempfile.TemporaryDirectory(prefix='vespertape-cookies-') as directory:
        target = Path(directory) / 'cookies.txt'
        shutil.copyfile(path, target)
        target.chmod(0o600)
        yield {'cookiefile': str(target)}


def number(value, integer=False):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
        return int(value) if integer else value
    return None


def public_url(value):
    if not isinstance(value, str):
        return None
    try:
        return UrlRequest(url=value).url
    except ValueError:
        return None


def item_from_info(info, source_url, index=None):
    flat = index is not None and info.get('_type') in ('url', 'url_transparent')
    formats = []
    for fmt in info.get('formats') or []:
        if not isinstance(fmt, dict) or not fmt.get('format_id') or not fmt.get('ext'):
            continue
        if fmt.get('vcodec') == 'none' and fmt.get('acodec') == 'none':
            continue
        formats.append(MediaFormat(
            id=str(fmt['format_id']), extension=str(fmt['ext']),
            video_codec=fmt.get('vcodec'), audio_codec=fmt.get('acodec'),
            width=number(fmt.get('width'), True), height=number(fmt.get('height'), True),
            filesize_bytes=number(fmt.get('filesize') or fmt.get('filesize_approx'), True),
        ))
    return PreviewItem(
        id=str(info.get('id') or index or 'media'),
        url=public_url(info.get('webpage_url')) or public_url(info.get('original_url')) or public_url(info.get('url')) or source_url,
        title=str(info.get('title') or 'Untitled media'), uploader=info.get('uploader') or info.get('channel'),
        thumbnail_url=public_url(info.get('thumbnail')), duration_seconds=number(info.get('duration')),
        playlist_index=index, formats=formats, formats_checked=not flat,
    )


def extract_preview(url: str, cookie_file=None) -> PreviewResponse:
    url = validate_target(url)
    options = {
        'quiet': True, 'no_warnings': True, 'logger': QuietLogger(),
        'skip_download': True, 'cachedir': False, 'socket_timeout': 15,
        'retries': 1, 'extractor_retries': 1, 'proxy': '',
        'js_runtimes': {'node': {}}, 'playlistend': 100, 'extract_flat': 'in_playlist',
    }
    try:
        with cookie_options(cookie_file) as cookies, PublicYoutubeDL({**options, **cookies}) as downloader:
            info = downloader.extract_info(url, download=False)
    except DownloadError as error:
        text = str(error).lower()
        if "confirm you're not a bot" in text or 'confirm you’re not a bot' in text:
            raise ApiException(422, 'youtube_verification_required',
                               'YouTube requires verification from the downloader server. Try again later; if it persists, server-side cookies may be required.') from None
        if '429' in text or 'too many requests' in text:
            raise ApiException(422, 'source_rate_limited',
                               'YouTube is limiting requests from the downloader server. Wait a while before trying again.') from None
        if any(word in text for word in ('private', 'login', 'sign in', 'members-only', 'authentication', '403')):
            raise ApiException(422, 'private_link', 'This link requires access or authentication.') from None
        if 'unsupported url' in text or 'no suitable extractor' in text:
            raise ApiException(422, 'unsupported_link', 'This link is not supported.') from None
        raise ApiException(422, 'preview_failed', 'Could not inspect this link. Check that it is available and try again.') from None
    if not isinstance(info, dict):
        raise ApiException(422, 'preview_failed', 'No media metadata was returned for this link.')
    if info.get('_type') in ('playlist', 'multi_video'):
        items = []
        for position, entry in enumerate(info.get('entries') or [], 1):
            if isinstance(entry, dict):
                index = number(entry.get('playlist_index'), True) or position
                items.append(item_from_info(entry, url, index))
        total = number(info.get('playlist_count') or info.get('n_entries'), True)
        return PreviewResponse(source_url=url, kind='playlist', title=str(info.get('title') or 'Playlist'), items=items, total_items=total)
    item = item_from_info(info, url)
    return PreviewResponse(source_url=url, kind='video', title=item.title, items=[item], total_items=1)
