# Setup and storage

[Documentation](README.md) · [Project overview](../README.md)

Run the complete app in Docker with automatic local download storage:

```sh
# macOS / Linux
python3 scripts/start.py
```

```powershell
# Windows (Python 3)
py scripts/start.py
```

The launcher locates your OS Downloads folder and creates a `VesperTape`
subfolder. Windows uses the system's known Downloads folder (including redirected
folders); Linux uses the XDG Downloads location when configured; macOS uses
`~/Downloads`. Single videos are saved in that folder; playlists use a subfolder named after the playlist. Downloads appear there automatically,
without clicking a browser Save link. Docker must run on the same computer.

The mapping is saved in the ignored `.env` file, preserving other settings.
Later `docker compose up --build -d` commands reuse it. To choose another folder,
run `python3 scripts/start.py --downloads "/path/to/folder"` (use `py` on Windows).
`--configure-only` writes the mapping without starting Docker. Python 3.9+ and
Docker Compose are required. Docker Desktop must allow access to the chosen folder.

Without running the launcher, Compose defaults to the project's `downloads/` folder.
On Linux, use the launcher to configure your UID/GID so downloaded files belong to
your user. A short-lived root storage initializer prepares volume permissions;
the API and workers run as the configured non-root user.

On first startup with a new mapped folder, existing files from the old Docker
volume's `/data/downloads` are copied there without overwriting existing files.
The old files and job database are preserved. The launcher stops the old worker
before migration; queued work resumes after startup.

The app and API are available at `http://localhost:8000`. Set `VESPERTAPE_API_PORT` to change the host port. Compose stores application data in the `vespertape-data` volume.

After API code changes, rerun `docker compose up --build -d`; Compose does not mount the source code. If the UI cannot load download settings, check `http://localhost:8000/api/settings`. A 404 can indicate an older container image; rebuild it and use Retry settings or refresh the page.

The container serves the built React app at the same URL.

## Related guides

- [Configuration](configuration.md)
- [Deployment](deployment.md)
- [Development and testing](development.md)
