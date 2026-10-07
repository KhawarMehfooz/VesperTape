import asyncio
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from api.contracts import CreateJobRequest
from api.database import Database
from api.jobs import JobStore
from api.settings import AppSettings
from api.worker import WorkerPool, download_options
from api.tests.test_errors import call


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = AppSettings(data_dir=Path(self.temp.name))
        self.settings.prepare_directories()
        self.database = Database(self.settings.data_dir / 'test.sqlite3')
        self.database.initialize()
        self.store = JobStore(self.database)

    def enqueue(self, **kwargs):
        return self.store.create(CreateJobRequest(url='https://www.youtube.com/watch?v=dQw4w9WgXcQ', **kwargs))

    def test_atomic_claims_and_fifo(self):
        jobs = [self.enqueue() for _ in range(12)]
        self.assertEqual(self.store.claim().id, jobs[0].id)
        with ThreadPoolExecutor(max_workers=6) as executor:
            claims = list(executor.map(lambda _: self.store.claim(), range(15)))
        ids = [job.id for job in claims if job]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {job.id for job in jobs[1:]})

    def test_persistence_and_restart_recovery(self):
        active, waiting, complete, failed = [self.enqueue() for _ in range(4)]
        self.store.claim()
        self.store.update(complete.id, status='complete', output_name='media.mp4')
        self.store.update(failed.id, status='failed')
        reopened = JobStore(Database(self.database.path))
        reopened.recover()
        self.assertEqual(reopened.get(active.id).status, 'queued')
        self.assertEqual(reopened.get(waiting.id).status, 'queued')
        self.assertEqual(reopened.get(complete.id).output_name, 'media.mp4')
        self.assertEqual(reopened.get(failed.id).status, 'failed')
        self.assertEqual(reopened.claim().id, active.id)

    def test_worker_success_progress_and_final_postprocessing_filename(self):
        job = self.enqueue()
        store = self.store
        class FakeDownloader:
            def __init__(self, options):
                self.options = options
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def extract_info(self, url, download):
                self.options['progress_hooks'][0]({
                    'status': 'finished', 'downloaded_bytes': 50, 'total_bytes': 100,
                    'speed': 10, 'eta': 5, 'info_dict': {'title': 'Test title'},
                })
                saved = store.get(job.id)
                assert saved.progress.percent == 50
                assert saved.progress.speed_bytes_per_second == 10
                assert saved.progress.eta_seconds == 5
                output = Path(self.options['paths']['home']) / 'converted.mp4'
                output.write_bytes(b'media')
                self.options['post_hooks'][0](str(output))
                return {'title': 'Test title'}
        pool = WorkerPool(self.store, self.settings, FakeDownloader)
        with patch('api.worker.validate_target'):
            pool.process(self.store.claim())
        saved = self.store.get(job.id)
        self.assertEqual(saved.status, 'complete')
        self.assertEqual(saved.output_name, 'converted.mp4')
        self.assertEqual(saved.progress.percent, 100)
        self.assertIsNone(saved.progress.eta_seconds)

    def test_background_worker_runs_one_job_and_shutdown_preserves_next(self):
        first, second = self.enqueue(), self.enqueue()
        entered = threading.Event()
        release = threading.Event()
        pool = WorkerPool(self.store, self.settings)
        def process(job):
            entered.set()
            release.wait(5)
            pool.stop_event.set()
            self.store.update(job.id, status='queued')
        with patch.object(pool, 'process', side_effect=process):
            pool.start()
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(len(pool.threads), 1)
                self.assertEqual(self.store.get(first.id).status, 'downloading')
                self.assertEqual(self.store.get(second.id).status, 'queued')
            finally:
                release.set()
                pool.stop()
        self.assertEqual(self.store.get(first.id).status, 'queued')

    def test_empty_download_is_failed_and_partial_files_survive_recovery(self):
        job = self.enqueue()
        directory = self.settings.download_dir / job.id
        directory.mkdir()
        partial = directory / 'media.mp4.part'
        partial.write_bytes(b'partial data')
        class EmptyDownloader:
            def __init__(self, options):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def extract_info(self, *args, **kwargs):
                return {'title': 'Empty playlist', 'entries': []}
        pool = WorkerPool(self.store, self.settings, EmptyDownloader)
        with patch('api.worker.validate_target'):
            pool.process(self.store.claim())
        self.assertEqual(self.store.get(job.id).status, 'failed')
        self.store.update(job.id, status='downloading')
        self.store.recover()
        self.assertEqual(partial.read_bytes(), b'partial data')
        self.assertEqual(self.store.get(job.id).status, 'queued')

    def test_failure_is_persisted_without_raw_exception(self):
        job = self.enqueue()
        pool = WorkerPool(self.store, self.settings)
        with patch('api.worker.validate_target', side_effect=RuntimeError('secret-token')):
            pool.process(self.store.claim())
        saved = self.store.get(job.id)
        self.assertEqual(saved.status, 'failed')
        self.assertEqual(saved.error.code, 'download_failed')
        self.assertNotIn('secret-token', saved.model_dump_json())

    def test_shutdown_requeues_and_exclusive_process_ownership(self):
        job = self.enqueue()
        pool = WorkerPool(self.store, self.settings)
        pool.stop_event.set()
        pool.process(self.store.claim())
        self.assertEqual(self.store.get(job.id).status, 'queued')
        # Use an empty queue so no real extraction occurs.
        self.store.update(job.id, status='complete')
        first = WorkerPool(self.store, self.settings)
        second = WorkerPool(self.store, self.settings)
        first.start()
        try:
            with self.assertRaises(RuntimeError):
                second.start()
        finally:
            first.stop()
        third = WorkerPool(self.store, self.settings)
        third.start()
        third.stop()

    def test_selection_and_conversion_options(self):
        job = self.enqueue(selection={'item_indices': [4, 2]}, settings={'mode': 'audio', 'format': 'mp3', 'filename': 'mix'})
        options = download_options(job, self.settings.download_dir / job.id)
        self.assertEqual(options['playlist_items'], '2,4')
        self.assertEqual(options['postprocessors'][0]['preferredcodec'], 'mp3')
        self.assertTrue(options['continuedl'])
        self.assertEqual(options['js_runtimes'], {'node': {}})
        self.assertIn('%(id)s', options['outtmpl'])
        video = download_options(self.enqueue(settings={'quality': '720p', 'format': 'mp4'}), self.settings.download_dir)
        self.assertIn('[height<=720]', video['format'])
        self.assertEqual(video['merge_output_format'], 'mp4')
        self.assertNotIn('playlist_items', video)

    def test_http_submission_defaults_validation_and_lookup(self):
        from api.main import app
        app.state.jobs = self.store
        app.state.settings = AppSettings(data_dir=self.settings.data_dir, allowed_modes=('audio',), allowed_formats=('mp3',))
        async def run():
            with patch('api.main.validate_target'):
                start, payload = await call(app, '/api/jobs', 'POST', b'{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}')
                self.assertEqual(start['status'], 201)
                self.assertEqual(payload['settings']['mode'], 'audio')
                self.assertEqual(payload['settings']['format'], 'mp3')
                start, listed = await call(app, '/api/jobs')
                self.assertEqual(len(listed['jobs']), 1)
                start, fetched = await call(app, '/api/jobs/' + payload['id'])
                self.assertEqual(fetched, payload)
                start, _ = await call(app, '/api/jobs/missing')
                self.assertEqual(start['status'], 404)
                start, _ = await call(app, '/api/jobs', 'POST', b'{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","settings":{"mode":"video"}}')
                self.assertEqual(start['status'], 422)
                start, _ = await call(app, '/api/jobs', 'POST', b'{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","settings":{"filename":"../escape"}}')
                self.assertEqual(start['status'], 422)
                app.state.settings = self.settings
                start, _ = await call(app, '/api/jobs', 'POST', b'{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","settings":{"format":"mp3"}}')
                self.assertEqual(start['status'], 422)
            with patch('api.preview.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]):
                start, payload = await call(app, '/api/jobs', 'POST', b'{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}')
                self.assertEqual(start['status'], 422)
                self.assertEqual(payload['error']['code'], 'blocked_target')
        asyncio.run(run())

    def test_sse_initial_snapshot_update_and_reconnect(self):
        from api.main import app, job_events
        app.state.jobs = self.store
        class Request:
            async def is_disconnected(self):
                return False
        async def run():
            response = await job_events(Request())
            self.assertEqual(response.media_type, 'text/event-stream')
            iterator = response.body_iterator
            initial = await anext(iterator)
            self.assertIn('event: jobs\ndata: {"jobs":[]}', initial)
            job = self.enqueue()
            update = await anext(iterator)
            data = json.loads(update.split('data: ', 1)[1])
            self.assertEqual(data['jobs'][0]['id'], job.id)
            await iterator.aclose()
            reconnected = (await job_events(Request())).body_iterator
            self.assertIn(job.id, await anext(reconnected))
            await reconnected.aclose()
        asyncio.run(run())
