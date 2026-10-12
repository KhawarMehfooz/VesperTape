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
from api.worker import WorkerPool, download_options, PlaylistLogger
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
        directory = self.settings.data_dir / 'work' / job.id
        directory.mkdir(parents=True)
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

    def test_playlist_unavailable_item_does_not_discard_completed_downloads(self):
        job = self.store.create(CreateJobRequest(url='https://www.youtube.com/playlist?list=PLtest123'))
        class Downloader:
            def __init__(self, options):
                self.options = options
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def extract_info(self, url, download):
                assert self.options['ignoreerrors'] is True
                self.options['logger'].error('ERROR: [youtube] secret-id: Video unavailable')
                output = Path(self.options['paths']['home']) / 'episode43.webm'
                output.write_bytes(b'media')
                self.options['post_hooks'][0](str(output))
                return {'title': 'Series'}
        pool = WorkerPool(self.store, self.settings, Downloader)
        with patch('api.worker.validate_target'):
            pool.process(self.store.claim())
        saved = self.store.get(job.id)
        self.assertEqual(saved.status, 'complete')
        self.assertEqual(saved.output_files, ['episode43.webm'])
        self.assertEqual(saved.error.code, 'playlist_items_skipped')
        self.assertNotIn('secret-id', saved.model_dump_json())
        self.assertIn('1 unavailable', saved.error.message)

    def test_playlist_logger_keeps_transport_and_verification_failures(self):
        for message, code in [('HTTP Error 403: secret', 'download_failed'),
                              ("Sign in to confirm you're not a bot: secret", 'youtube_verification_required'),
                              ('HTTP Error 429: secret', 'source_rate_limited')]:
            with self.subTest(code=code):
                logger = PlaylistLogger()
                logger.error(message)
                self.assertEqual(logger.unavailable, 0)
                self.assertEqual(logger.failure.code, code)
                self.assertNotIn('secret', logger.failure.model_dump_json())

    def test_playlist_folder_and_current_item_thumbnails(self):
        job = self.store.create(CreateJobRequest(url='https://www.youtube.com/playlist?list=PLtest123'))
        store = self.store
        class Downloader:
            def __init__(self, options):
                self.options = options
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def extract_info(self, url, download):
                for index in (1, 2):
                    thumbnail = f'https://i.ytimg.com/vi/video{index}/hqdefault.jpg'
                    self.options['progress_hooks'][0]({'status': 'finished',
                        'info_dict': {'title': f'Episode {index}', 'thumbnail': thumbnail,
                                      'playlist_title': 'Series: A / B'}})
                    current = store.get(job.id)
                    assert current.title == f'Episode {index}'
                    assert current.thumbnail_url == thumbnail
                    output = Path(self.options['paths']['home']) / f'episode{index}.mp4'
                    output.write_bytes(b'media')
                    self.options['post_hooks'][0](str(output))
                return {'_type': 'playlist', 'title': 'Series: A / B'}
        pool = WorkerPool(self.store, self.settings, Downloader)
        with patch('api.worker.validate_target'):
            pool.process(self.store.claim())
        saved = self.store.get(job.id)
        self.assertEqual(saved.status, 'complete')
        self.assertEqual(saved.output_folder, 'Series_ A _ B')
        self.assertEqual([item.title for item in saved.downloaded_items], ['Episode 1', 'Episode 2'])
        for name in saved.output_files:
            self.assertTrue((self.settings.download_dir / saved.output_folder / name).is_file())
            self.assertFalse((self.settings.download_dir / name).exists())

    def test_completed_playlist_migration_and_folder_file_access(self):
        from api.main import app, completed_file
        from api.errors import ApiException
        job = self.store.create(CreateJobRequest(url='https://www.youtube.com/playlist?list=PLtest123'))
        name = 'Episode_1 [n7Hi2k6aHBw] 1.mp4'
        (self.settings.download_dir / name).write_bytes(b'media')
        self.store.update(job.id, status='complete', title='Series', output_files=[name],
                          output_name=name, output_directory='root')
        pool = WorkerPool(self.store, self.settings)
        pool.migrate_outputs()
        pool.migrate_outputs()
        saved = self.store.get(job.id)
        self.assertEqual(saved.output_folder, 'Series')
        self.assertEqual(saved.downloaded_items[0].title, 'Episode 1')
        self.assertEqual(saved.downloaded_items[0].thumbnail_url, 'https://i.ytimg.com/vi/n7Hi2k6aHBw/hqdefault.jpg')
        app.state.jobs, app.state.settings = self.store, self.settings
        self.assertEqual(completed_file(job.id, name).path, self.settings.download_dir / 'Series' / name)
        self.store.update(job.id, output_folder='../escape')
        with self.assertRaises(ApiException):
            completed_file(job.id, name)

    def test_playlist_folder_rejects_symlinks_and_preserves_collision(self):
        job = self.enqueue()
        directory = self.settings.data_dir / 'work' / job.id
        directory.mkdir(parents=True)
        (directory / 'episode.mp4').write_bytes(b'new')
        destination = self.settings.download_dir / 'Series'
        destination.symlink_to(self.settings.data_dir, target_is_directory=True)
        job.output_folder = 'Series'
        pool = WorkerPool(self.store, self.settings)
        with self.assertRaises(RuntimeError):
            pool.publish(job, directory)
        destination.unlink()
        destination.mkdir()
        (destination / 'episode.mp4').write_bytes(b'original')
        names = pool.publish(job, directory)
        self.assertEqual(names, ['episode (1).mp4'])
        self.assertEqual((destination / 'episode.mp4').read_bytes(), b'original')

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

    def test_controls_persist_and_removal_advances_feed(self):
        from api.errors import ApiException
        job = self.enqueue()
        self.assertEqual(self.store.action(job.id, 'pause').status, 'paused')
        self.store.recover()
        self.assertEqual(self.store.get(job.id).status, 'paused')
        self.assertEqual(self.store.action(job.id, 'resume').status, 'queued')
        self.assertEqual(self.store.action(job.id, 'cancel').status, 'canceled')
        self.assertEqual(self.store.action(job.id, 'retry').status, 'queued')
        with self.assertRaises(ApiException):
            self.store.action(job.id, 'resume')
        with self.assertRaises(ApiException):
            self.store.remove(job.id)
        self.store.action(job.id, 'cancel')
        revision = self.store.snapshot()[0]
        self.store.remove(job.id)
        self.assertGreater(self.store.snapshot()[0], revision)
        self.assertEqual(self.store.snapshot()[1], [])

    def test_worker_cannot_overwrite_pause_or_cancel(self):
        from api.errors import ApiException
        for action, status in [('pause', 'paused'), ('cancel', 'canceled')]:
            job = self.enqueue()
            pool = WorkerPool(self.store, self.settings)
            pool.active.add(job.id)
            class ControlledDownloader:
                def __init__(self, options):
                    self.options = options
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def extract_info(self, *args, **kwargs):
                    pool.action(job.id, action)
                    with self_outer.assertRaises(ApiException):
                        pool.action(job.id, 'resume' if action == 'pause' else 'retry')
                    self.options['progress_hooks'][0]({'status': 'finished'})
            self_outer = self
            pool.downloader_factory = ControlledDownloader
            with patch('api.worker.validate_target'):
                pool.process(self.store.claim())
            self.assertEqual(self.store.get(job.id).status, status)
            self.store.update(job.id, expected_status='downloading', status='complete')
            self.assertEqual(self.store.get(job.id).status, status)
            pool.active.clear()
            if action == 'pause':
                pool.action(job.id, 'cancel')

    def test_action_http_and_safe_file_retrieval(self):
        from api.main import app, completed_file
        from api.errors import ApiException
        app.state.jobs = self.store
        app.state.settings = self.settings
        app.state.workers = WorkerPool(self.store, self.settings)
        job = self.enqueue()
        async def run():
            start, payload = await call(app, f'/api/jobs/{job.id}/actions', 'POST', b'{"action":"pause"}')
            self.assertEqual(start['status'], 200)
            self.assertEqual(payload['status'], 'paused')
            start, _ = await call(app, f'/api/jobs/{job.id}/actions', 'POST', b'{"action":"pause"}')
            self.assertEqual(start['status'], 409)
            start, _ = await call(app, '/api/jobs/missing/actions', 'POST', b'{"action":"cancel"}')
            self.assertEqual(start['status'], 404)
        asyncio.run(run())
        with self.assertRaises(ApiException):
            completed_file(job.id, 'media.mp4')
        directory = self.settings.download_dir / job.id
        directory.mkdir()
        (directory / 'media.mp4').write_bytes(b'media')
        self.store.update(job.id, status='complete', output_name='media.mp4', output_files=['media.mp4', 'link.mp4', '../secret'])
        response = completed_file(job.id, 'media.mp4')
        self.assertEqual(response.path, directory / 'media.mp4')
        self.assertIn('attachment;', response.headers['content-disposition'])
        (directory / 'link.mp4').symlink_to(self.database.path)
        for name in ['link.mp4', '../secret', '.archive', 'missing.mp4']:
            with self.assertRaises(ApiException):
                completed_file(job.id, name)
        self.store.remove(job.id)
        self.assertTrue((directory / 'media.mp4').exists())
        with self.assertRaises(ApiException):
            completed_file(job.id, 'media.mp4')

    def test_http_control_lifecycle_and_terminal_removal(self):
        from api.main import app
        app.state.jobs = self.store
        app.state.settings = self.settings
        app.state.workers = WorkerPool(self.store, self.settings)
        job = self.enqueue()

        async def run():
            start, _ = await call(app, f'/api/jobs/{job.id}', 'DELETE')
            self.assertEqual(start['status'], 409)
            for action, expected in [('pause', 'paused'), ('resume', 'queued'),
                                     ('cancel', 'canceled'), ('retry', 'queued')]:
                start, payload = await call(app, f'/api/jobs/{job.id}/actions', 'POST',
                                            json.dumps({'action': action}).encode())
                self.assertEqual(start['status'], 200)
                self.assertEqual(payload['status'], expected)
                self.assertEqual(self.store.get(job.id).status, expected)
            start, _ = await call(app, f'/api/jobs/{job.id}/actions', 'POST', b'{"action":"retry"}')
            self.assertEqual(start['status'], 409)
            start, _ = await call(app, f'/api/jobs/{job.id}/actions', 'POST', b'{"action":"unknown"}')
            self.assertEqual(start['status'], 422)
            await call(app, f'/api/jobs/{job.id}/actions', 'POST', b'{"action":"cancel"}')
            start, _ = await call(app, f'/api/jobs/{job.id}', 'DELETE')
            self.assertEqual(start['status'], 204)
            start, _ = await call(app, f'/api/jobs/{job.id}')
            self.assertEqual(start['status'], 404)
        asyncio.run(run())

    def test_flat_outputs_migration_collision_and_internal_partials(self):
        from api.main import app, completed_file
        pool = WorkerPool(self.store, self.settings)
        first, second, paused = self.enqueue(), self.enqueue(), self.enqueue()
        for job in [first, second]:
            directory = self.settings.download_dir / job.id
            directory.mkdir()
            (directory / 'media.mp4').write_bytes(job.id.encode())
            (directory / '.archive').write_text('archive')
            self.store.update(job.id, status='complete', output_name='media.mp4')
        partial_directory = self.settings.download_dir / paused.id
        partial_directory.mkdir()
        (partial_directory / 'unfinished.mp4.part').write_bytes(b'partial')
        self.store.action(paused.id, 'pause')
        pool.migrate_outputs()
        self.assertEqual((self.settings.download_dir / 'media.mp4').read_bytes(), first.id.encode())
        self.assertEqual((self.settings.download_dir / 'media (1).mp4').read_bytes(), second.id.encode())
        self.assertFalse(any(path.is_dir() for path in self.settings.download_dir.iterdir()))
        self.assertTrue((self.settings.data_dir / 'work' / paused.id / 'unfinished.mp4.part').exists())
        self.assertEqual(self.store.get(paused.id).status, 'paused')
        app.state.jobs = self.store
        app.state.settings = self.settings
        self.assertEqual(completed_file(second.id, 'media (1).mp4').path, self.settings.download_dir / 'media (1).mp4')
        pool.migrate_outputs()
        self.assertEqual(len(list(self.settings.download_dir.iterdir())), 2)

    def test_legacy_folder_without_history_preserves_media(self):
        job = self.enqueue()
        directory = self.settings.download_dir / job.id
        directory.mkdir()
        (directory / 'old.mp4').write_bytes(b'old media')
        self.store.action(job.id, 'cancel')
        self.store.remove(job.id)
        pool = WorkerPool(self.store, self.settings)
        pool.migrate_outputs()
        self.assertEqual((self.settings.download_dir / 'old.mp4').read_bytes(), b'old media')
        self.assertFalse(directory.exists())
