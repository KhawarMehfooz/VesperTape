# VesperTape

A self-hosted YouTube downloader for videos, audio, and playlists, powered by
yt-dlp and FFmpeg, with a desktop-inspired web interface.

## Screenshot

![VesperTape interface](docs/images/preview.jpg)

## Features

- Preview YouTube links and choose a whole playlist, one item, or a range.
- Download video or audio with quality and format controls.
- Save playlists in folders named after the playlist.
- Follow a persistent queue with thumbnails, progress, pause/resume, cancel, and retry.
- Customize subtitles, metadata, thumbnails, chapters, filenames, and network settings.

## Quick start

Install Docker with Compose and Python 3.9+, then run from the repository root:

```sh
# macOS / Linux
python3 scripts/start.py
```

```powershell
# Windows
py scripts/start.py
```

Open **[localhost:8000](http://localhost:8000)**.

The launcher saves files to your OS Downloads folder under `VesperTape` and
records the mapping in `.env`. Playlists get their own named subfolders.
Docker must run on the computer where you want the files saved.

To choose a different destination:

```sh
python3 scripts/start.py --downloads "/path/to/folder"
```

Use `py` on Windows. For other settings, copy [`.env.example`](.env.example)
to `.env` before your first launch, or merge values into your existing `.env`.
See [configuration](docs/configuration.md) and [setup and storage](docs/setup.md).

## Using the app

Paste a YouTube link, choose **Preview**, select audio or video and your settings,
then choose **Add to downloads**. Open completed files in your download folder.
Unavailable playlist items are skipped with a warning. Removing a history entry
leaves its files on disk.

## Documentation

See the [documentation index](docs/README.md) for usage, configuration,
deployment, troubleshooting, development, and the API reference.
