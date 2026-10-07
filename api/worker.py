"""Background downloads with cooperative shutdown and isolated resumable output."""
import threading
import time
import fcntl
import shutil
import re
from pathlib import Path
from uuid import UUID
from urllib.parse import parse_qs, urlsplit
from yt_dlp.utils import match_filter_func

if __package__:
    from .contracts import ApiError, JobProgress, DownloadedItem
    from .preview import PublicYoutubeDL, QuietLogger, validate_target, number, cookie_options, public_url
    from .errors import ApiException
else:
    from contracts import ApiError, JobProgress, DownloadedItem
    from preview import PublicYoutubeDL, QuietLogger, validate_target, number, cookie_options, public_url
    from errors import ApiException


def playlist_folder(title):
    # A single portable component, bounded in UTF-8 bytes.
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title).strip(' .')
    name = name.encode('utf-8')[:180].decode('utf-8', errors='ignore').rstrip(' .') or 'Playlist'
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *[f'COM{i}' for i in range(1, 10)], *[f'LPT{i}' for i in range(1, 10)]}:
        name = '_' + name
    return name


def media_thumbnail(info):
    thumbnail = public_url(info.get('thumbnail'))
    media_id = str(info.get('id') or '')
    return thumbnail or (f'https://i.ytimg.com/vi/{media_id}/hqdefault.jpg'
                         if re.fullmatch(r'[A-Za-z0-9_-]{11}', media_id) else None)


def legacy_items(names):
    items = []
    for name in names:
        if Path(name).suffix.lower() not in {'.mp4', '.webm', '.mkv', '.mp3', '.m4a', '.flac', '.wav', '.opus', '.ogg', '.aac', '.mov'}:
            continue
        match = re.search(r'\[([A-Za-z0-9_-]{11})\]', name)
        title = name[:match.start()].strip().replace('_', ' ') if match else Path(name).stem
        items.append(DownloadedItem(filename=name, title=title,
            thumbnail_url=media_thumbnail({'id': match.group(1)}) if match else None))
    return items


class PlaylistLogger(QuietLogger):
    """Keep safe failure categories, never raw extractor text."""
    def __init__(self):
        self.unavailable = 0
        self.failure = None

    def error(self, message):
        text = str(message).lower()
        if "confirm you're not a bot" in text or 'confirm you’re not a bot' in text:
            self.failure = ApiError(code='youtube_verification_required',
                message='YouTube requires verification from the downloader server. Server-side cookies may be required.')
        elif '429' in text or 'too many requests' in text:
            self.failure = ApiError(code='source_rate_limited',
                message='YouTube is limiting requests from the downloader server. Wait before retrying.')
        elif any(phrase in text for phrase in ('video unavailable', 'private video', 'video has been removed',
                                               'not available in your country', 'members-only')):
            self.unavailable += 1
        else:
            self.failure = ApiError(code='download_failed',
                message='Could not download this media. Check availability and the selected settings.')


class Interrupted(Exception):
    pass


def download_options(job, directory):
    settings = job.settings
    stem = settings.filename or settings.output_template or '%(title).120B'
    # Include original playlist index and media ID to avoid collisions, including
    # when the user chooses a filename for multiple playlist entries.
    template = f'{stem} [%(id)s] %(playlist_index|0)s.%(ext)s'
    options = {
        'quiet': True, 'no_warnings': True, 'logger': QuietLogger(),
        'cachedir': False, 'proxy': '', 'socket_timeout': 15,
        'js_runtimes': {'node': {}},
        'retries': 3, 'fragment_retries': 3, 'extractor_retries': 1,
        'continuedl': True, 'overwrites': False, 'ignoreerrors': False,
        'paths': {'home': str(directory)}, 'outtmpl': template,
        'restrictfilenames': True, 'windowsfilenames': True, 'trim_file_name': 200,
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
    options.update(
        writesubtitles=settings.subtitles, writeautomaticsub=settings.automatic_captions,
        subtitleslangs=settings.subtitle_languages, subtitlesformat='best',
        writethumbnail=settings.save_thumbnail or settings.embed_thumbnail,
        retries=settings.retry_count, fragment_retries=settings.retry_count,
        ratelimit=settings.rate_limit, concurrent_fragment_downloads=settings.fragment_concurrency,
        proxy=settings.proxy or '',
        http_headers={line.partition(':')[0]: line.partition(':')[2].strip() for line in settings.http_headers},
        playliststart=settings.playlist_start, playlistend=settings.playlist_end,
    )
    if job.selection.item_indices:
        indices = [i for i in job.selection.item_indices if i >= settings.playlist_start
                   and (settings.playlist_end is None or i <= settings.playlist_end)]
        if not indices:
            raise ApiException(422, 'empty_selection', 'Playlist filters exclude all selected items.')
        options['playlist_items'] = ','.join(map(str, sorted(indices)))
    filters = []
    if settings.minimum_duration is not None:
        filters.append(f'duration >= {settings.minimum_duration}')
    if settings.maximum_duration is not None:
        filters.append(f'duration <= {settings.maximum_duration}')
    if filters:
        options['match_filter'] = match_filter_func(' & '.join(filters))
    processors = options.setdefault('postprocessors', [])
    if settings.remux != 'auto':
        processors[:] = [p for p in processors if p['key'] != 'FFmpegVideoRemuxer']
        processors.append({'key': 'FFmpegVideoRemuxer', 'preferedformat': settings.remux})
    if settings.subtitle_format != 'best' and (settings.subtitles or settings.automatic_captions):
        processors.append({'key': 'FFmpegSubtitlesConvertor', 'format': settings.subtitle_format})
    if settings.embed_subtitles:
        processors.append({'key': 'FFmpegEmbedSubtitle'})
    if settings.embed_metadata or settings.embed_chapters:
        processors.append({'key': 'FFmpegMetadata', 'add_metadata': settings.embed_metadata,
                           'add_chapters': settings.embed_chapters})
    if settings.split_chapters:
        options['outtmpl'] = {'default': template,
            'chapter': f'{stem} [%(id)s] %(playlist_index|0)s - %(section_number)03d.%(ext)s'}
        processors.append({'key': 'FFmpegSplitChapters', 'force_keyframes': False})
    if settings.embed_thumbnail:
        processors.append({'key': 'EmbedThumbnail', 'already_have_thumbnail': settings.save_thumbnail})
    for argument in settings.custom_options:
        key = {'--prefer-free-formats': 'prefer_free_formats', '--no-playlist': 'noplaylist',
               '--playlist-reverse': 'playlistreverse', '--check-formats': 'check_formats'}[argument]
        options[key] = True
    return options


class WorkerPool:
    def __init__(self, store, settings, downloader_factory=PublicYoutubeDL):
        self.store = store
        self.settings = settings
        self.downloader_factory = downloader_factory
        self.stop_event = threading.Event()
        self.threads = []
        self.lock_file = None
        self.control_lock = threading.Lock()
        self.active = set()

    def start(self):
        # Recovery must never requeue a download owned by another API process.
        self.lock_file = (self.settings.data_dir / 'worker.lock').open('a')
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock_file.close()
            raise RuntimeError('Only one API process may own this download queue') from None
        try:
            self.migrate_outputs()
            self.store.recover()
            for index in range(self.settings.worker_count):
                thread = threading.Thread(target=self._run, name=f'download-{index}', daemon=True)
                self.threads.append(thread)
                thread.start()
        except Exception:
            self.stop()
            raise

    def check_work_directory(self, directory):
        root = self.settings.data_dir
        work = root / 'work'
        if (work.is_symlink() or directory.is_symlink()
                or not directory.resolve().is_relative_to(root.resolve())
                or directory.parent != work):
            raise RuntimeError('Unsafe job storage directory')

    def publish(self, job, directory, mappings=None):
        """Reserve filenames exclusively so simultaneous/repeated jobs never overwrite."""
        self.check_work_directory(directory)
        names = []
        destination = self.settings.download_dir
        if job and job.output_folder:
            if playlist_folder(job.output_folder) != job.output_folder:
                raise RuntimeError('Unsafe playlist folder')
            destination = destination / job.output_folder
            if destination.is_symlink() or not destination.resolve().is_relative_to(self.settings.download_dir.resolve()):
                raise RuntimeError('Unsafe playlist folder')
            destination.mkdir(exist_ok=True)
        sources = [path for path in directory.iterdir() if path.is_file()
                   and not path.is_symlink() and not path.name.startswith('.')
                   and not path.name.endswith(('.part', '.ytdl', '.temp'))]
        if not sources:
            raise RuntimeError('No completed output')
        for source in sources:
            index = 0
            while True:
                suffix = '' if index == 0 else f' ({index})'
                target = destination / f'{source.stem}{suffix}{source.suffix}'
                try:
                    output = target.open('xb')
                except FileExistsError:
                    rule = job.settings.file_conflict if job else 'rename'
                    if rule == 'skip':
                        # Do not create history links to an unrelated existing file.
                        break
                    if rule == 'fail':
                        raise ApiException(409, 'file_conflict', 'A download filename already exists.')
                    index += 1
                    continue
                try:
                    with output, source.open('rb') as input_file:
                        shutil.copyfileobj(input_file, output)
                except Exception:
                    target.unlink(missing_ok=True)
                    raise
                names.append(target.name)
                if mappings is not None:
                    mappings[source.name] = target.name
                break
        return names

    def migrate_outputs(self):
        work = self.settings.data_dir / 'work'
        if work.is_symlink():
            raise RuntimeError('Unsafe job storage directory')
        work.mkdir(exist_ok=True)
        jobs = self.store.snapshot()[1]
        for job in jobs:
            legacy = self.settings.download_dir / job.id
            directory = work / job.id
            self.check_work_directory(directory)
            if legacy.is_dir() and not legacy.is_symlink():
                if directory.exists():
                    raise RuntimeError('Both legacy and internal job directories exist')
                shutil.move(str(legacy), str(directory))
            if job.status == 'complete' and job.output_directory == 'root' and not job.output_folder and 'list' in parse_qs(urlsplit(job.source_url).query):
                folder = playlist_folder(job.playlist_title or job.title or 'Playlist')
                target_dir = self.settings.download_dir / folder
                if target_dir.is_symlink():
                    raise RuntimeError('Unsafe playlist folder')
                target_dir.mkdir(exist_ok=True)
                names = []
                for name in job.output_files:
                    source = self.settings.download_dir / name
                    if Path(name).name != name or source.is_symlink():
                        raise RuntimeError('Unsafe recorded output')
                    target = target_dir / name
                    if source.is_file():
                        index = 0
                        while True:
                            try:
                                output = target.open('xb')
                                break
                            except FileExistsError:
                                index += 1
                                target = target_dir / f'{source.stem} ({index}){source.suffix}'
                        try:
                            with output, source.open('rb') as input_file:
                                shutil.copyfileobj(input_file, output)
                        except Exception:
                            target.unlink(missing_ok=True)
                            raise
                        source.unlink()
                    elif not target.is_file() or target.is_symlink():
                        continue
                    names.append(target.name)
                job = self.store.update(job.id, output_folder=folder, output_files=names,
                    output_name=names[-1] if names else None, downloaded_items=legacy_items(names))
            if job.status == 'complete' and not job.downloaded_items:
                job = self.store.update(job.id, downloaded_items=legacy_items(job.output_files))
            if job.status == 'complete' and job.output_directory == 'job' and directory.is_dir():
                names = self.publish(job, directory)
                self.store.update(job.id, output_directory='root', output_files=names, output_name=names[-1])
                shutil.rmtree(directory)

        # Removed history entries can leave legacy folders with valuable files.
        known = {job.id for job in jobs}
        for legacy in self.settings.download_dir.iterdir():
            if not legacy.is_dir() or legacy.is_symlink() or legacy.name in known:
                continue
            try:
                UUID(legacy.name)
            except ValueError:
                continue
            directory = work / legacy.name
            self.check_work_directory(directory)
            if directory.exists():
                raise RuntimeError('Both legacy and internal job directories exist')
            shutil.move(str(legacy), str(directory))
            sources = [p for p in directory.iterdir() if p.is_file() and not p.name.startswith('.')
                       and not p.name.endswith(('.part', '.ytdl', '.temp'))]
            if sources:
                self.publish(None, directory)
                for source in sources:
                    source.unlink()

    def stop(self):
        self.stop_event.set()
        for thread in self.threads:
            thread.join()
        if self.lock_file is not None and not self.lock_file.closed:
            self.lock_file.close()

    def _run(self):
        while not self.stop_event.is_set():
            with self.control_lock:
                job = self.store.claim()
                if job is not None:
                    self.active.add(job.id)
            if job is None:
                self.stop_event.wait(0.25)
                continue
            try:
                self.process(job)
            finally:
                with self.control_lock:
                    self.active.discard(job.id)

    def action(self, job_id, action):
        with self.control_lock:
            if action in {'resume', 'retry'} and job_id in self.active:
                raise ApiException(409, 'worker_stopping', 'Download is stopping. Try again shortly.')
            return self.store.action(job_id, action)

    def remove(self, job_id):
        with self.control_lock:
            if job_id in self.active:
                raise ApiException(409, 'worker_stopping', 'Download is stopping. Try again shortly.')
            self.store.remove(job_id)

    def process(self, job):
        last_write = 0
        current_media = {}
        directory = self.settings.data_dir / 'work' / job.id

        def check_stop():
            if self.stop_event.is_set() or self.store.get(job.id).status != 'downloading':
                raise Interrupted()

        def progress(data):
            nonlocal last_write, current_media
            check_stop()
            current = time.monotonic()
            if data.get('status') != 'finished' and current - last_write < 0.5:
                return
            last_write = current
            downloaded = number(data.get('downloaded_bytes'), True) or 0
            total = number(data.get('total_bytes') or data.get('total_bytes_estimate'), True)
            info = data.get('info_dict') or {}
            current_media = info
            self.store.update(job.id, expected_status='downloading', title=str(info.get('title') or job.title or 'Untitled media'),
                thumbnail_url=media_thumbnail(info),
                playlist_title=info.get('playlist_title') or job.playlist_title,
                progress=JobProgress(downloaded_bytes=downloaded, total_bytes=total,
                    percent=min(100, downloaded / total * 100) if total else None,
                    speed_bytes_per_second=number(data.get('speed')), eta_seconds=number(data.get('eta'))))

        def final_file(filename):
            check_stop()
            path = Path(filename).resolve()
            if not path.is_relative_to(directory.resolve()):
                raise RuntimeError('Output escaped job directory')
            current = self.store.get(job.id)
            self.store.update(job.id, expected_status='downloading', output_name=path.name,
                output_files=list(dict.fromkeys([*current.output_files, path.name])),
                downloaded_items=[*[item for item in current.downloaded_items if item.filename != path.name],
                    DownloadedItem(filename=path.name, title=str(current_media.get('title') or current.title or path.stem),
                                   thumbnail_url=media_thumbnail(current_media))])

        try:
            check_stop()
            self.check_work_directory(directory)
            directory.mkdir(parents=True, exist_ok=True)
            validate_target(job.source_url)
            if job.settings.proxy:
                validate_target(job.settings.proxy.replace('socks5://', 'http://', 1))
            options = download_options(job, directory)
            playlist_logger = None
            if 'list' in parse_qs(urlsplit(job.source_url).query) and not options.get('noplaylist'):
                playlist_logger = PlaylistLogger()
                options.update(ignoreerrors=True, logger=playlist_logger)
            archive = self.settings.data_dir / 'download-archive.txt'
            local_archive = directory / '.archive'
            if job.settings.use_archive:
                with self.control_lock:
                    previous = local_archive.read_text() if local_archive.exists() else ''
                    shared = archive.read_text() if archive.exists() else ''
                    local_archive.write_text(shared + previous)

            options.update(progress_hooks=[progress], post_hooks=[final_file],
                           postprocessor_hooks=[lambda data: check_stop()])
            with cookie_options(self.settings.cookie_file if job.settings.use_cookie_file else None) as cookies, self.downloader_factory({**options, **cookies}) as downloader:
                info = downloader.extract_info(job.source_url, download=True)
            check_stop()
            if playlist_logger is not None and playlist_logger.failure is not None:
                raise ApiException(422, playlist_logger.failure.code, playlist_logger.failure.message)
            # An empty selection, or playlist consisting only of unavailable
            # entries, must not be reported as a successful download.
            outputs = [path for path in directory.iterdir() if path.is_file() and not path.name.startswith('.') and not path.name.endswith(('.part', '.ytdl', '.temp'))]
            if not outputs and not (job.settings.use_archive or job.settings.minimum_duration is not None
                                    or job.settings.maximum_duration is not None):
                raise RuntimeError('No completed output')
            current = self.store.get(job.id)
            warning = None
            if playlist_logger is not None and playlist_logger.unavailable:
                warning = ApiError(code='playlist_items_skipped',
                    message=f'Skipped {playlist_logger.unavailable} unavailable playlist item(s). Other selected items were downloaded.')
            with self.control_lock:
                check_stop()
                folder = current.output_folder
                if (info or {}).get('_type') in ('playlist', 'multi_video'):
                    folder = folder or playlist_folder(str(info.get('title') or current.playlist_title or 'Playlist'))
                current = self.store.update(job.id, output_folder=folder)
                mappings = {}
                names = self.publish(current, directory, mappings) if outputs else []
                items = [item.model_copy(update={'filename': mappings[item.filename]})
                         for item in (current.downloaded_items or legacy_items(current.output_files)) if item.filename in mappings]
                if job.settings.use_archive and local_archive.exists():
                    previous = archive.read_text().splitlines() if archive.exists() else []
                    lines = sorted(set(previous + local_archive.read_text().splitlines()))
                    temporary = archive.with_suffix('.tmp')
                    temporary.write_text(''.join(line + '\n' for line in lines if line))
                    temporary.replace(archive)
                self.store.update(job.id, expected_status='downloading', status='complete', title=str((info or {}).get('title') or current.title or 'Untitled media'),
                    output_name=names[-1] if names else None, output_files=names, output_directory='root',
                    output_folder=folder, downloaded_items=items,
                    progress=current.progress.model_copy(update={'percent': 100, 'speed_bytes_per_second': None, 'eta_seconds': None}), error=warning)
            shutil.rmtree(directory)
        except Exception as error:
            if self.stop_event.is_set() or isinstance(error, Interrupted):
                self.store.update(job.id, expected_status='downloading', status='queued', progress=JobProgress(), error=None)
            else:
                public_error = error.error if isinstance(error, ApiException) else ApiError(
                    code='download_failed', message='Could not download this media. Check availability and the selected settings.')
                self.store.update(job.id, expected_status='downloading', status='failed', error=public_error,
                    progress=self.store.get(job.id).progress.model_copy(update={'speed_bytes_per_second': None, 'eta_seconds': None}))
