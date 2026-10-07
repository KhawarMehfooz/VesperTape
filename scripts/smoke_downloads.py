"""Opt-in live media and restart checks in an isolated Compose project."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='Public short YouTube video you are permitted to download')
    parser.add_argument('--timeout', type=int, default=300, help='Seconds per download')
    parser.add_argument('--image', help='Use an existing image instead of building')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    with tempfile.TemporaryDirectory(prefix='vespertape-smoke-') as temporary:
        directory = Path(temporary)
        project = f'vespertape-smoke-{os.getpid()}'
        service = {
            'build': {'context': str(ROOT), 'dockerfile': 'Dockerfile'},
            'ports': ['127.0.0.1::8000'],
            'environment': {'VESPERTAPE_DATA_DIR': '/data', 'VESPERTAPE_DOWNLOAD_DIR': '/data/downloads'},
            'volumes': ['smoke-data:/data'], 'init': True,
            'security_opt': ['no-new-privileges:true'], 'cap_drop': ['ALL'],
        }
        if args.image:
            service.pop('build')
            service['image'] = args.image
        config = directory / 'compose.json'
        config.write_text(json.dumps({'services': {'vespertape': service}, 'volumes': {'smoke-data': {}}}))
        compose = ['docker', 'compose', '-p', project, '-f', str(config)]

        def command(*parts, capture=False):
            return subprocess.run([*compose, *parts], check=True, text=True,
                                  stdout=subprocess.PIPE if capture else None).stdout

        base = ''

        def request(path, body=None):
            req = Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                          headers={'Content-Type': 'application/json'})
            try:
                with urlopen(req, timeout=60) as response:
                    return json.load(response)
            except HTTPError as error:
                payload = json.load(error)
                raise RuntimeError(payload['error']['message']) from None

        def ready():
            nonlocal base
            port = command('port', 'vespertape', '8000', capture=True).strip().rsplit(':', 1)[1]
            base = f'http://127.0.0.1:{port}'
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    request('/api/health')
                    return
                except (URLError, OSError):
                    time.sleep(1)
            raise RuntimeError('API did not become ready')

        def wait_for(job_id, predicate):
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                job = request(f'/api/jobs/{job_id}')
                if job['status'] == 'failed':
                    raise RuntimeError(job['error']['message'])
                if predicate(job):
                    return job
                if job['status'] in {'complete', 'canceled'}:
                    raise RuntimeError('Job finished before the required recovery checkpoint; use a longer video')
                time.sleep(0.5)
            raise RuntimeError('Timed out waiting for download state')

        try:
            command('up', '-d', *([] if args.image else ['--build']))
            port = command('port', 'vespertape', '8000', capture=True).strip().rsplit(':', 1)[1]
            base = f'http://127.0.0.1:{port}'
            ready()
            request('/api/preview', {'url': args.url})
            saved = []
            for mode, container in [('video', 'mp4'), ('audio', 'mp3')]:
                job = request('/api/jobs', {'url': args.url, 'settings': {
                    'mode': mode, 'format': container, 'quality': '480p' if mode == 'video' else 'best',
                    'embed_metadata': True, 'rate_limit': 131072,
                }})
                if mode == 'video':
                    wait_for(job['id'], lambda value: value['status'] == 'downloading' and value['progress']['downloaded_bytes'] > 0)
                    # A forced stop exercises crash recovery, retaining partial files and SQLite.
                    command('kill', '-s', 'SIGKILL', 'vespertape')
                    command('up', '-d')
                    ready()
                job = wait_for(job['id'], lambda value: value['status'] == 'complete')
                assert job['output_files'], 'Completed job has no media files'
                for filename in job['output_files']:
                    probe = command('exec', '-T', 'vespertape', 'ffprobe', '-v', 'error',
                                    '-show_streams', '-of', 'json', f'/data/downloads/{filename}', capture=True)
                    types = {stream['codec_type'] for stream in json.loads(probe)['streams']}
                    assert 'audio' in types, 'Missing audio stream'
                    assert ('video' in types) == (mode == 'video'), 'Unexpected video stream'
                    with urlopen(base + f"/api/jobs/{job['id']}/files/{quote(filename, safe='')}", timeout=60) as response:
                        assert response.read(1), 'Empty file response'
                saved.append(job)
                print(f'{mode}: complete; FFprobe and file retrieval passed', flush=True)
            command('restart', 'vespertape')
            ready()
            for job in saved:
                current = request(f"/api/jobs/{job['id']}")
                assert current['status'] == 'complete' and current['output_files'] == job['output_files']
                for filename in current['output_files']:
                    with urlopen(base + f"/api/jobs/{job['id']}/files/{quote(filename, safe='')}", timeout=60) as response:
                        assert response.read(1)
            print('PASS: live video/audio, FFmpeg outputs, active recovery, and persistent history/files')
        finally:
            command('down', '-v', '--remove-orphans')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, AssertionError, URLError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'Smoke check failed: {error}') from None
