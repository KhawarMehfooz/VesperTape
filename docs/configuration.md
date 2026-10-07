# Configuration

[Documentation](README.md) · [Project overview](../README.md)

Use [`.env.example`](../.env.example) as the template for Compose configuration:

```sh
cp .env.example .env
```

If `.env` already exists, merge the values you need instead of replacing it.
The launcher maintains the download-folder and UID/GID values and preserves your
other settings. Keep `.env` private; on macOS/Linux use `chmod 600 .env`.
Compose passes worker count and option allowlists through to the API. The optional
cookie mount requires both Compose files, as described in the cookie guide.
The template also lists local-only API paths as commented examples.

Configuration is read from environment variables at API startup. Invalid values
or unusable storage directories stop startup. Restart the API after changes.

| Variable | Default | Meaning |
| --- | --- | --- |
| `VESPERTAPE_DATA_DIR` | `data` locally, `/data` in Docker | Application storage |
| `VESPERTAPE_DOWNLOAD_DIR` | `<data directory>/downloads` locally; `/downloads` in Compose | Download storage inside the API host/container |
| `VESPERTAPE_HOST_DOWNLOAD_DIR` | `./downloads` before launcher setup | Compose bind-mount source on your computer; launcher selects Downloads/VesperTape |
| `VESPERTAPE_UID` / `VESPERTAPE_GID` | `10001` | Compose runtime user/group; launcher uses your Linux UID/GID |
| `VESPERTAPE_ACCESS_PASSWORD` | Unset | Optional single-user password (minimum 16 characters); username `vespertape` |
| `VESPERTAPE_API_PORT` | `8000` | Compose host port for the app and API |
| `VESPERTAPE_HOST_COOKIE_FILE` | Unset | Host cookie file used by the optional Compose override |
| `VESPERTAPE_COOKIE_FILE` | Unset | Protected cookie-file path on the API host; see [server cookies](usage.md#protected-server-cookies) |
| `VESPERTAPE_BIND_ADDRESS` | `127.0.0.1` | Compose host interface for the published port |
| `VESPERTAPE_WORKER_COUNT` | `1` | Positive integer; concurrent downloads (default: one) |
| `VESPERTAPE_ALLOWED_MODES` | `["video","audio"]` | JSON array of allowed modes |
| `VESPERTAPE_ALLOWED_QUALITIES` | `["best","1080p","720p","480p"]` | JSON array of allowed qualities |
| `VESPERTAPE_ALLOWED_FORMATS` | `["auto","mp4","webm","mp3","m4a","flac","wav"]` | JSON array of allowed formats |

Option arrays must be nonempty, unique, and use the supported values above.
Their first entries become public defaults. `GET /api/settings` exposes these
defaults, allowed values, worker count, and the `default` destination name.
Directory paths stay on the server; paths are resolved relative to the API's
working directory and created on startup. Use distinct data and download paths.
Compose downloads persist in the configured host bind mount; application data
persists separately in the `/data` named volume.
For custom paths in Docker, add the environment variables and matching writable
volume mounts to `docker-compose.yml`. Local execution reads exported environment
variables; it does not automatically load `.env` files.

Run configuration checks with `python -m unittest api.tests.test_settings`.

## Related guides

- [Setup and storage](setup.md)
- [Protected server cookies](usage.md#protected-server-cookies)
- [Deployment](deployment.md)
