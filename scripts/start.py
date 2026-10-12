"""Start Docker Compose with downloads mapped to the current user's Downloads."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def downloads_directory():
    system = platform.system()
    if system == 'Windows':
        # FOLDERID_Downloads follows relocated/OneDrive-backed known folders.
        class GUID(ctypes.Structure):
            _fields_ = [('data1', ctypes.c_uint32), ('data2', ctypes.c_uint16),
                        ('data3', ctypes.c_uint16), ('data4', ctypes.c_ubyte * 8)]
        guid = GUID.from_buffer_copy(uuid.UUID('374DE290-123F-4565-9164-39C4925E467B').bytes_le)
        pointer = ctypes.c_void_p()
        shell = ctypes.windll.shell32
        result = shell.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(pointer))
        if result != 0:
            raise RuntimeError('Windows could not locate the Downloads folder')
        try:
            return Path(ctypes.wstring_at(pointer.value))
        finally:
            ctypes.windll.ole32.CoTaskMemFree(pointer)
    if system == 'Linux':
        if shutil.which('xdg-user-dir'):
            result = subprocess.run(['xdg-user-dir', 'DOWNLOAD'], capture_output=True, text=True, check=True)
            if result.stdout.strip():
                return Path(result.stdout.strip())
        config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'user-dirs.dirs'
        if config.is_file():
            for line in config.read_text().splitlines():
                if line.startswith('XDG_DOWNLOAD_DIR='):
                    value = line.split('=', 1)[1].strip().strip('"')
                    return Path(value.replace('${HOME}', str(Path.home())).replace('$HOME', str(Path.home())))
    return Path.home() / 'Downloads'


def configure(destination):
    destination = destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if not os.access(destination, os.W_OK | os.X_OK):
        raise RuntimeError(f'Download folder is not writable: {destination}')
    # Linux bind mounts enforce host UID/GID. Docker Desktop translates ownership.
    linux = platform.system() == 'Linux'
    values = {
        'VESPERTAPE_HOST_DOWNLOAD_DIR': destination.as_posix(),
        'VESPERTAPE_UID': str(os.getuid() if linux else 10001),
        'VESPERTAPE_GID': str(os.getgid() if linux else 10001),
    }
    env_file = ROOT / '.env'
    lines = env_file.read_text().splitlines() if env_file.exists() else []
    lines = [line for line in lines if line.split('=', 1)[0].strip().removeprefix('export ') not in values]
    for key, value in values.items():
        if '\n' in value or '\r' in value:
            raise ValueError('Download path cannot contain a newline')
        lines.append(f'{key}={json.dumps(value.replace("$", "$$"), ensure_ascii=False)}')
    env_file.write_text('\n'.join(lines) + '\n')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--downloads', type=Path, help='Override the automatic Downloads/VesperTape folder')
    parser.add_argument('--configure-only', action='store_true', help='Write the mapping without starting Docker')
    args = parser.parse_args()
    try:
        destination = configure(args.downloads or downloads_directory() / 'VesperTape')
        print(f'Downloads will be saved to: {destination}', flush=True)
        if not args.configure_only:
            # Explicit values prevent an inherited shell variable overriding the mapping.
            env = os.environ.copy()
            env.update(VESPERTAPE_HOST_DOWNLOAD_DIR=destination.as_posix(),
                       VESPERTAPE_UID=str(os.getuid() if platform.system() == 'Linux' else 10001),
                       VESPERTAPE_GID=str(os.getgid() if platform.system() == 'Linux' else 10001))
            # Stop the old worker before copying files or changing volume ownership.
            subprocess.run(['docker', 'compose', 'stop', 'vespertape'], cwd=ROOT, env=env, check=True)
            subprocess.run(['docker', 'compose', 'up', '--build', '-d'], cwd=ROOT, env=env, check=True)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Could not start VesperTape: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
