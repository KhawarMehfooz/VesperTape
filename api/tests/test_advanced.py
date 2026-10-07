import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError
from yt_dlp import YoutubeDL

from api.contracts import CreateJobRequest, DownloadSettings
from api.errors import ApiException
from api.preview import cookie_options, extract_preview
from api.settings import AppSettings
from api.worker import download_options, WorkerPool
from api.database import Database
from api.jobs import JobStore
from api.tests.test_errors import call

URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'


class AdvancedTests(unittest.TestCase):
    def test_untrusted_options_and_paths_rejected(self):
        for payload in [
            {'custom_options': ['--exec=touch /tmp/unsafe']},
            {'custom_options': ['--cookies=/etc/passwd']},
            {'output_template': '../%(title)s'}, {'output_template': '%(title)s/%(id)s'},
            {'output_template': '%(unknown)s'}, {'output_template': '%(title)999999999s'},
            {'proxy': 'http://user:password@proxy.example'},
            {'http_headers': ['User-Agent: valid\r\nCookie: secret']},
            {'http_headers': ['Authorization: secret']},
            {'http_headers': ['User-Agent: a', 'user-agent: b']},
            {'subtitle_languages': ['.*']}, {'retry_count': 21}, {'fragment_concurrency': 17},
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                DownloadSettings(**payload)

    def test_enqueue_configuration_rules(self):
        settings = AppSettings()
        for payload in [{'use_cookie_file': True}, {'playlist_start': 4, 'playlist_end': 2},
                        {'minimum_duration': 60, 'maximum_duration': 20},
                        {'filename': 'name', 'output_template': '%(title)s'},
                        {'mode': 'audio', 'embed_subtitles': True}, {'mode': 'audio', 'remux': 'mkv'}]:
            with self.subTest(payload=payload), self.assertRaises(ApiException):
                settings.validate_download_settings(DownloadSettings(**payload))
        with patch('api.preview.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]), self.assertRaises(ApiException):
            settings.validate_download_settings(DownloadSettings(proxy='http://localhost:8080'))

    def test_api_rejects_custom_options_before_persistence(self):
        from api.main import app
        with tempfile.TemporaryDirectory() as directory:
            settings = AppSettings(data_dir=Path(directory))
            settings.prepare_directories()
            database = Database(settings.data_dir / 'test.sqlite3')
            database.initialize()
            store = JobStore(database)
            app.state.settings = settings
            app.state.jobs = store
            with patch('api.main.validate_target'):
                start, response = asyncio.run(call(app, '/api/jobs', 'POST', json.dumps({
                    'url': URL, 'settings': {'custom_options': ['--exec=secret-command']}
                }).encode()))
                self.assertEqual(start['status'], 422)
                self.assertNotIn('secret-command', json.dumps(response))
                self.assertEqual(store.snapshot()[1], [])
                start, response = asyncio.run(call(app, '/api/jobs', 'POST', json.dumps({
                    'url': URL, 'settings': {'subtitles': True, 'retry_count': 5,
                        'custom_options': ['--check-formats']}
                }).encode()))
                self.assertEqual(start['status'], 201)
                reopened = JobStore(Database(database.path)).get(response['id'])
                self.assertTrue(reopened.settings.subtitles)
                self.assertEqual(reopened.settings.retry_count, 5)
                self.assertEqual(reopened.settings.custom_options, ['--check-formats'])

    def test_postprocessors_and_filters_use_real_yt_dlp(self):
        job = CreateJobRequest(url=URL, selection={'item_indices': [1, 2, 3]}, settings={
            'subtitles': True, 'automatic_captions': True, 'subtitle_format': 'srt',
            'embed_subtitles': True, 'embed_metadata': True, 'embed_chapters': True,
            'split_chapters': True, 'embed_thumbnail': True, 'remux': 'mkv',
            'playlist_start': 2, 'playlist_end': 3, 'minimum_duration': 30,
            'maximum_duration': 120, 'retry_count': 5, 'rate_limit': 1000,
            'fragment_concurrency': 4, 'http_headers': ['Accept-Language: en'],
            'output_template': '%(uploader)s - %(title).120B',
            'custom_options': ['--prefer-free-formats']})
        options = download_options(job, Path('/tmp/work'))
        self.assertEqual(options['playlist_items'], '2,3')
        self.assertIsNone(options['match_filter']({'duration': 60}))
        self.assertIsNotNone(options['match_filter']({'duration': 10}))
        self.assertEqual(options['retries'], 5)
        self.assertEqual(options['ratelimit'], 1000)
        self.assertEqual(options['http_headers'], {'Accept-Language': 'en'})
        with YoutubeDL(options) as downloader:
            self.assertTrue(downloader.params['prefer_free_formats'])

    def test_cookie_mount_is_protected_and_copied(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / 'cookies.txt'
            content = '# Netscape HTTP Cookie File\n'
            cookie.write_text(content)
            cookie.chmod(0o600)
            settings = AppSettings(cookie_file=cookie)
            self.assertTrue(settings.public_settings().cookie_file_available)
            self.assertNotIn(str(cookie), settings.public_settings().model_dump_json())
            with cookie_options(cookie) as options:
                copy = Path(options['cookiefile'])
                self.assertNotEqual(copy, cookie)
                copy.write_text('changed')
            self.assertFalse(copy.exists())
            self.assertEqual(cookie.read_text(), content)
            cookie.chmod(0o644)
            with self.assertRaises(ValidationError):
                AppSettings(cookie_file=cookie)

    def test_preview_uses_configured_cookie_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / 'cookies.txt'
            cookie.write_text('# Netscape HTTP Cookie File\n')
            cookie.chmod(0o600)
            with patch('api.preview.validate_target', side_effect=lambda url: url), patch('api.preview.PublicYoutubeDL') as factory:
                factory.return_value.__enter__.return_value.extract_info.return_value = {'id': 'media', 'title': 'Media'}
                extract_preview(URL, cookie)
                copy = Path(factory.call_args.args[0]['cookiefile'])
                self.assertNotEqual(cookie, copy)
            self.assertFalse(copy.exists())

    def test_file_conflicts_and_shared_archive_survive_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = AppSettings(data_dir=Path(temp))
            settings.prepare_directories()
            database = Database(settings.data_dir / 'test.sqlite3')
            database.initialize()
            store = JobStore(database)
            pool = WorkerPool(store, settings)
            directory = settings.data_dir / 'work' / 'test'
            directory.mkdir(parents=True)
            (directory / 'media.mp4').write_bytes(b'new')
            target = settings.download_dir / 'media.mp4'
            target.write_bytes(b'original')
            for rule, expected in [('rename', ['media (1).mp4']), ('skip', [])]:
                job = store.create(CreateJobRequest(url=URL, settings={'file_conflict': rule}))
                self.assertEqual(pool.publish(job, directory), expected)
                self.assertEqual(target.read_bytes(), b'original')
            job = store.create(CreateJobRequest(url=URL, settings={'file_conflict': 'fail'}))
            with self.assertRaises(ApiException):
                pool.publish(job, directory)

            class FakeDownloader:
                def __init__(self, options):
                    self.options = options
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def extract_info(self, url, download):
                    archive = Path(self.options['download_archive'])
                    if 'youtube media' not in archive.read_text():
                        (Path(self.options['paths']['home']) / 'archive.mp4').write_bytes(b'media')
                        archive.write_text('youtube media\n')
                    return {'title': 'Media'}

            pool = WorkerPool(store, settings, FakeDownloader)
            with patch('api.worker.validate_target'):
                for iteration in range(2):
                    job = store.create(CreateJobRequest(url=URL, settings={'use_archive': True}))
                    store.update(job.id, status='downloading')
                    pool.process(store.get(job.id))
                    saved = store.get(job.id)
                    self.assertEqual(saved.status, 'complete')
                    self.assertEqual(len(saved.output_files), 1 if iteration == 0 else 0)
                    pool = WorkerPool(JobStore(Database(database.path)), settings, FakeDownloader)
            self.assertEqual((settings.data_dir / 'download-archive.txt').read_text(), 'youtube media\n')
