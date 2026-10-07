import asyncio
import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from api.contracts import CreateJobRequest, PreviewRequest
from api.tests.test_errors import call


class YouTubeLinkTests(unittest.TestCase):
    def test_valid_media_links(self):
        for url in (
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'http://youtube.com/watch?v=dQw4w9WgXcQ&t=30',
            'https://youtu.be/dQw4w9WgXcQ?si=shared',
            'https://m.youtube.com/shorts/dQw4w9WgXcQ',
            'https://youtube.com/live/dQw4w9WgXcQ',
            'https://music.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ',
            'https://youtube.com/playlist?list=PLtestPlaylist123',
            'https://youtube.com/watch?v=dQw4w9WgXcQ&list=PLtestPlaylist123',
        ):
            for model in (PreviewRequest, CreateJobRequest):
                with self.subTest(url=url, model=model):
                    self.assertEqual(model(url=' '+url+' ').url, url)

    def test_invalid_and_lookalike_links(self):
        for url in (
            'https://example.com/watch?v=dQw4w9WgXcQ',
            'https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ',
            'https://notyoutube.com/watch?v=dQw4w9WgXcQ',
            'https://youtube.com', 'https://youtube.com/@creator',
            'https://youtube.com/watch', 'https://youtube.com/watch?v=short',
            'https://youtu.be/dQw4w9WgXcQ/extra',
            'https://youtube.com/watch?v=dQw4w9WgXcQ&v=dQw4w9WgXcQ',
            'https://youtube.com/watch?v=dQw4w9WgXcQ%0A',
            'https://youtube.com/playlist?list=',
            'https://youtube.com/watch?v=dQw4w9WgXcQ&list=',
            'https://youtube.com:8443/watch?v=dQw4w9WgXcQ',
            'https://user@youtube.com/watch?v=dQw4w9WgXcQ',
            'https://@youtube.com/watch?v=dQw4w9WgXcQ',
            'ftp://youtube.com/watch?v=dQw4w9WgXcQ',
            'youtube.com/watch?v=dQw4w9WgXcQ',
        ):
            for model in (PreviewRequest, CreateJobRequest):
                with self.subTest(url=url, model=model), self.assertRaises(ValidationError):
                    model(url=url)

    def test_both_endpoints_reject_before_extraction_or_queueing(self):
        from api.main import app
        with patch('api.main.extract_preview') as extract, patch('api.main.validate_target') as target:
            for endpoint in ('/api/preview', '/api/jobs'):
                start, payload = asyncio.run(call(app, endpoint, 'POST', json.dumps({'url': 'https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ'}).encode()))
                self.assertEqual(start['status'], 422)
                self.assertEqual(payload['error']['details'][0]['location'], ['body', 'url'])
            extract.assert_not_called()
            target.assert_not_called()
