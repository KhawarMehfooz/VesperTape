import asyncio
import base64
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from pydantic import ValidationError

from api.security import AccessProtection
from api.settings import AppSettings
from api.worker import WorkerPool


class SecurityTests(unittest.TestCase):
    password = 'a-long-private-password'

    def request(self, path='/', credential=None, method='GET', headers=(), enabled=True):
        app = FastAPI()
        app.state.settings = AppSettings(access_password=self.password if enabled else None)
        app.add_middleware(AccessProtection)

        @app.api_route('/{path:path}', methods=['GET', 'POST'], include_in_schema=False)
        def route(path):
            if path == 'failure':
                raise RuntimeError('private-cookie-data')
            return {'ok': True}

        messages = []
        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        async def send(message):
            messages.append(message)
        supplied = [(b'host', b'localhost:8000'), *headers]
        if credential is not None:
            supplied.append((b'authorization', credential))
        scope = {'type': 'http', 'method': method, 'path': path, 'scheme': 'http',
                 'query_string': b'', 'headers': supplied, 'server': ('localhost', 8000),
                 'client': ('127.0.0.1', 1234), 'root_path': ''}
        asyncio.run(app(scope, receive, send))
        return messages[0], b''.join(m.get('body', b'') for m in messages)

    def basic(self, username='vespertape', password=None):
        return b'Basic ' + base64.b64encode(f'{username}:{password or self.password}'.encode())

    def test_all_surfaces_are_protected_except_health(self):
        for path in ('/', '/assets/app.js', '/docs', '/openapi.json', '/api/settings',
                     '/api/jobs/events', '/api/jobs/id/files/video.mp4', '/missing'):
            with self.subTest(path=path):
                start, body = self.request(path)
                self.assertEqual(start['status'], 401)
                self.assertIn(b'Basic realm=', dict(start['headers'])[b'www-authenticate'])
                self.assertNotIn(self.password.encode(), body)
                self.assertEqual(self.request(path, self.basic())[0]['status'], 200)
        self.assertEqual(self.request('/api/health')[0]['status'], 200)
        self.assertEqual(self.request(enabled=False)[0]['status'], 200)

    def test_unexpected_failure_is_sanitized_before_server_logging(self):
        start, body = self.request('/failure', self.basic())
        self.assertEqual(start['status'], 500)
        self.assertNotIn(b'private-cookie-data', body)

    def test_invalid_credentials(self):
        for credential in (b'Bearer secret', b'Basic !!!', b'Basic /w==', b'Basic YWJj',
                           self.basic(password='incorrect'), self.basic(username='other')):
            self.assertEqual(self.request(credential=credential)[0]['status'], 401)

    def test_cross_site_mutations_are_blocked(self):
        for headers in ([(b'origin', b'https://evil.example')], [(b'origin', b'null')],
                        [(b'sec-fetch-site', b'cross-site')]):
            for enabled in (True, False):
                start, _ = self.request(method='POST', credential=self.basic(), headers=headers, enabled=enabled)
                self.assertEqual(start['status'], 403)
        for origin in (b'http://localhost:8000', None):
            headers = [(b'origin', origin)] if origin else []
            self.assertEqual(self.request(method='POST', credential=self.basic(), headers=headers)[0]['status'], 200)

    def test_password_configuration_does_not_expose_secret(self):
        settings = AppSettings.from_env({'VESPERTAPE_ACCESS_PASSWORD': self.password})
        self.assertNotIn(self.password, repr(settings))
        self.assertNotIn(self.password, settings.model_dump_json())
        self.assertNotIn(self.password, settings.public_settings().model_dump_json())
        self.assertIsNone(AppSettings.from_env({'VESPERTAPE_ACCESS_PASSWORD': ''}).access_password)
        with self.assertRaises(ValidationError) as error:
            AppSettings(access_password='short-secret')
        self.assertNotIn('short-secret', str(error.exception))

    def test_work_directory_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = AppSettings(data_dir=root / 'data', download_dir=root / 'downloads')
            settings.prepare_directories()
            outside = root / 'outside'
            outside.mkdir()
            pool = WorkerPool(SimpleNamespace(), settings)
            work = settings.data_dir / 'work'
            work.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                pool.check_work_directory(work / 'job')
            work.unlink()
            work.mkdir()
            (work / 'job').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                pool.publish(None, work / 'job')
            self.assertEqual(list(outside.iterdir()), [])
