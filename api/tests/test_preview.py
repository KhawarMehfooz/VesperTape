import asyncio
import json
import unittest
from unittest.mock import patch

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from api.errors import ApiException
from api.preview import extract_preview, validate_target, PublicYoutubeDL
from api.tests.test_errors import call

PUBLIC = [(2, 1, 6, '', ('93.184.216.34', 443))]
VIDEO = {'id': 'abc', 'title': 'A video', 'uploader': 'Creator', 'duration': 90,
         'webpage_url': 'https://example.com/watch/abc', 'thumbnail': 'https://example.com/thumb.jpg',
         'formats': [{'format_id': 'v1', 'ext': 'mp4', 'vcodec': 'h264', 'acodec': 'aac', 'height': 720, 'filesize': 1024},
                     {'format_id': 'storyboard', 'ext': 'mhtml', 'vcodec': 'none', 'acodec': 'none'}]}


class PreviewTests(unittest.TestCase):
    def extract(self, info=None, error=None):
        with patch('api.preview.socket.getaddrinfo', return_value=PUBLIC), patch('api.preview.PublicYoutubeDL') as factory:
            downloader = factory.return_value.__enter__.return_value
            downloader.extract_info.return_value = info
            downloader.extract_info.side_effect = error
            result = extract_preview('https://example.com/video')
            downloader.extract_info.assert_called_once_with('https://example.com/video', download=False)
            self.assertTrue(factory.call_args.args[0]['skip_download'])
            self.assertEqual(factory.call_args.args[0]['js_runtimes'], {'node': {}})
            self.assertFalse(factory.call_args.args[0].get('ignore_no_formats_error', False))
            return result

    def test_video_metadata_and_formats(self):
        result = self.extract(VIDEO)
        self.assertEqual(result.kind, 'video')
        item = result.items[0]
        self.assertEqual((item.title, item.uploader, item.duration_seconds), ('A video', 'Creator', 90))
        self.assertEqual(len(item.formats), 1)
        self.assertEqual(item.formats[0].filesize_bytes, 1024)

    def test_playlist_preserves_indexes_and_total(self):
        result = self.extract({'_type': 'playlist', 'title': 'Collection', 'playlist_count': 200,
                               'entries': [dict(VIDEO, playlist_index=2), None, dict(VIDEO, id='def', playlist_index=5)]})
        self.assertEqual(result.kind, 'playlist')
        self.assertEqual(result.total_items, 200)
        self.assertEqual([item.playlist_index for item in result.items], [2, 5])

    def test_playlist_preview_uses_flat_entries_without_claiming_formats(self):
        with patch('api.preview.socket.getaddrinfo', return_value=PUBLIC), patch('api.preview.PublicYoutubeDL') as factory:
            downloader = factory.return_value.__enter__.return_value
            downloader.extract_info.return_value = {
                '_type': 'playlist', 'title': 'Series', 'playlist_count': 51,
                'entries': [{'_type': 'url', 'id': 'n7Hi2k6aHBw',
                             'url': 'https://www.youtube.com/watch?v=n7Hi2k6aHBw',
                             'title': 'Episode 1', 'playlist_index': 3}],
            }
            result = extract_preview('https://www.youtube.com/playlist?list=PLtest123')
            self.assertEqual(factory.call_args.args[0].get('extract_flat'), 'in_playlist')
            self.assertEqual(result.items[0].url, 'https://www.youtube.com/watch?v=n7Hi2k6aHBw')
            self.assertEqual(result.items[0].playlist_index, 3)
            self.assertFalse(result.items[0].formats_checked)
            self.assertEqual(result.items[0].formats, [])
            self.assertEqual(result.total_items, 51)

    def test_empty_and_no_format_states(self):
        self.assertEqual(self.extract({'_type': 'playlist', 'entries': []}).items, [])
        result = self.extract({'id': 'empty', 'duration': float('nan'), 'thumbnail': 'file:///secret'})
        self.assertEqual(result.items[0].formats, [])
        self.assertIsNone(result.items[0].duration_seconds)
        self.assertIsNone(result.items[0].thumbnail_url)

    def test_errors_are_classified_without_leaking_details(self):
        for message, code in [('Unsupported URL: secret', 'unsupported_link'), ('Video is private: secret', 'private_link'), ('network secret', 'preview_failed'), ('Sign in to confirm you’re not a bot: secret', 'youtube_verification_required'), ('HTTP Error 429: Too Many Requests: secret', 'source_rate_limited')]:
            with self.subTest(code=code), self.assertRaises(ApiException) as caught:
                self.extract(error=DownloadError(message))
            self.assertEqual(caught.exception.error.code, code)
            self.assertNotIn('secret', caught.exception.error.message)

    def test_local_mixed_and_unresolved_targets_are_blocked(self):
        for address in ('127.0.0.1', '10.1.2.3', '169.254.169.254', '::1', '::ffff:127.0.0.1', '192.168.1.1'):
            with self.subTest(address=address), patch('api.preview.socket.getaddrinfo', return_value=PUBLIC + [(2, 1, 6, '', (address, 443))]), self.assertRaises(ApiException):
                validate_target('https://example.com')
        with patch('api.preview.socket.getaddrinfo', return_value=[]), self.assertRaises(ApiException):
            validate_target('https://example.com')
        for url in ('file:///tmp/test', 'ftp://example.com', 'https://user:pass@example.com'):
            with self.assertRaises(ApiException):
                validate_target(url)

    def test_extractor_requests_checked_before_transport(self):
        with PublicYoutubeDL({'quiet': True}) as downloader, patch('api.preview.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]), patch.object(YoutubeDL, 'urlopen') as transport:
            with self.assertRaises(ApiException):
                downloader.urlopen('http://localhost/private')
            transport.assert_not_called()

    def test_endpoint_contract_and_validation(self):
        from api.main import app
        with patch('api.main.extract_preview', return_value=self.extract(VIDEO)):
            start, payload = asyncio.run(call(app, '/api/preview', 'POST', json.dumps({'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'}).encode()))
        self.assertEqual(start['status'], 200)
        self.assertEqual(payload['items'][0]['title'], 'A video')
        start, payload = asyncio.run(call(app, '/api/preview', 'POST', b'{"url":"file:///tmp/video"}'))
        self.assertEqual(start['status'], 422)
        self.assertEqual(payload['error']['code'], 'validation_error')
        with patch('api.preview.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]):
            start, payload = asyncio.run(call(app, '/api/preview', 'POST', b'{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'))
        self.assertEqual(payload['error']['code'], 'blocked_target')
