"""Background downloads with cooperative shutdown and isolated resumable output."""
import threading
import time
import fcntl
from pathlib import Path

if __package__:
    from .contracts import ApiError, JobProgress
    from .preview import PublicYoutubeDL, QuietLogger, validate_target, number
    from .errors import ApiException
else:
    from contracts import ApiError, JobProgress
    from preview import PublicYoutubeDL, QuietLogger, validate_target, number
    from errors import ApiException


class Interrupted(Exception):
    pass


def download_options(job, directory):
    settings = job.settings
    stem = settings.filename or '%(title).120B'
    # Include original playlist index and media ID to avoid collisions, including
    # when the user chooses a filename for multiple playlist entries.
    template = f'{stem} [%(id)s] %(playlist_index|0)s.%(ext)s'
    options = {
        'quiet': True, 'no_warnings': True, 'logger': QuietLogger(),
        'cachedir': False, 'proxy': '', 'socket_timeout': 15,
        'retries': 3, 'fragment_retries': 3, 'extractor_retries': 1,
        'continuedl': True, 'overwrites': False, 'ignoreerrors': False,
        'paths': {'home': str(directory)}, 'outtmpl': template,
        'restrictfilenames': True,
        'download_archive': str(directory / '.archive'),
    }
    if job.selection.item_indices:
        options['playlist_items'] = ','.join(map(str, sorted(job.selection.item_indices)))
    if settings.mode == 'audio':
        options['format'] = 'bestaudio/best'
        if settings.format != 'auto':
            options['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': settings.format}]
    else:
        limit = '' if settings.quality == 'best' else f'[height<={settings.quality[:-1]}]'
        options['format'] = f'bestvideo{limit}+bestaudio/best{limit}'
        if settings.format != 'auto':
            options['merge_output_format'] = settings.format
            options['postprocessors'] = [{'key': 'FFmpegVideoRemuxer', 'preferedformat': settings.format}]
    return options


class WorkerPool:
    def __init__(self, store, settings, downloader_factory=PublicYoutubeDL):
        self.store = store
        self.settings = settings
        self.downloader_factory = downloader_factory
        self.stop_event = threading.Event()
        self.threads = []
        self.lock_file = None

    def start(self):
        # Recovery must never requeue a download owned by another API process.
        self.lock_file = (self.settings.data_dir / 'worker.lock').open('a')
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock_file.close()
            raise RuntimeError('Only one API process may own this download queue') from None
        try:
            self.store.recover()
            for index in range(self.settings.worker_count):
                thread = threading.Thread(target=self._run, name=f'download-{index}', daemon=True)
                self.threads.append(thread)
                thread.start()
        except Exception:
            self.stop()
            raise

    def stop(self):
        self.stop_event.set()
        for thread in self.threads:
            thread.join()
        if self.lock_file is not None and not self.lock_file.closed:
            self.lock_file.close()

    def _run(self):
        while not self.stop_event.is_set():
            job = self.store.claim()
            if job is None:
                self.stop_event.wait(0.25)
                continue
            self.process(job)

    def process(self, job):
        last_write = 0
        directory = self.settings.download_dir / job.id

        def check_stop():
            if self.stop_event.is_set():
                raise Interrupted()

        def progress(data):
            nonlocal last_write
            check_stop()
            current = time.monotonic()
            if data.get('status') != 'finished' and current - last_write < 0.5:
                return
            last_write = current
            downloaded = number(data.get('downloaded_bytes'), True) or 0
            total = number(data.get('total_bytes') or data.get('total_bytes_estimate'), True)
            info = data.get('info_dict') or {}
            self.store.update(job.id, title=str(info.get('title') or job.title or 'Untitled media'),
                progress=JobProgress(downloaded_bytes=downloaded, total_bytes=total,
                    percent=min(100, downloaded / total * 100) if total else None,
                    speed_bytes_per_second=number(data.get('speed')), eta_seconds=number(data.get('eta'))))

        def final_file(filename):
            check_stop()
            path = Path(filename).resolve()
            if not path.is_relative_to(directory.resolve()):
                raise RuntimeError('Output escaped job directory')
            self.store.update(job.id, output_name=path.name)

        try:
            check_stop()
            directory.mkdir(parents=True, exist_ok=True)
            validate_target(job.source_url)
            options = download_options(job, directory)
            options.update(progress_hooks=[progress], post_hooks=[final_file],
                           postprocessor_hooks=[lambda data: check_stop()])
            with self.downloader_factory(options) as downloader:
                info = downloader.extract_info(job.source_url, download=True)
            check_stop()
            # An empty selection, or playlist consisting only of unavailable
            # entries, must not be reported as a successful download.
            outputs = [path for path in directory.iterdir() if path.is_file() and not path.name.startswith('.') and not path.name.endswith(('.part', '.ytdl', '.temp'))]
            if not outputs:
                raise RuntimeError('No completed output')
            current = self.store.get(job.id)
            self.store.update(job.id, status='complete', title=str((info or {}).get('title') or current.title or 'Untitled media'),
                output_name=current.output_name or outputs[0].name,
                progress=current.progress.model_copy(update={'percent': 100, 'speed_bytes_per_second': None, 'eta_seconds': None}), error=None)
        except Exception as error:
            if self.stop_event.is_set() or isinstance(error, Interrupted):
                self.store.update(job.id, status='queued', progress=JobProgress(), error=None)
            else:
                public_error = error.error if isinstance(error, ApiException) else ApiError(
                    code='download_failed', message='Could not download this media. Check availability and the selected settings.')
                self.store.update(job.id, status='failed', error=public_error,
                    progress=self.store.get(job.id).progress.model_copy(update={'speed_bytes_per_second': None, 'eta_seconds': None}))
