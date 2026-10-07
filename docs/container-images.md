# Published container images

The `Test and publish Docker image` GitHub Actions workflow runs on pushes to
`master` (including PR merges), pull requests targeting `master`, and manual
runs. PRs only build and test; publishing is restricted to `master`. API tests,
generated contract checks, frontend browser tests, and a smoke test of the
packaged app must pass before publishing.

Images are published to `ghcr.io/khawarmehfooz/vespertape` with `latest`, `master`,
and `sha-<full-commit>` tags. Docker automatically selects AMD64 or ARM64.
Use the image digest shown in the workflow summary for immutable deployments.
The image includes SBOM and build provenance attestations. Actions are pinned
to commit SHAs; Dependabot proposes weekly action and base-image updates.
BuildKit caches dependency and intermediate layers between runs. The frontend
build runs on the builder's native architecture even for ARM64 output, and only
compiled frontend assets and API source go into the runtime image.

## First publication

1. Commit and push the workflow to `master`. GitHub Actions uses the built-in
   `GITHUB_TOKEN` with package write permission; no registry password is needed.
2. After the first successful publication, open your GitHub profile's Packages,
   select `vespertape`, and under Package settings change visibility to **Public**
   so users can pull without logging in. GitHub creates new packages as private
   by default, even for public repositories.
3. Verify anonymous access with `docker manifest inspect
   ghcr.io/khawarmehfooz/vespertape:latest` from a client not logged into GHCR.

If repository or organization policy disables Actions or package publishing,
enable it before running the workflow. If a package with this name already
exists, ensure this repository has Actions access to it.

## Deploy and update

Use the commands in the [project README](../README.md). The image Compose file
uses prebuilt images for both the app and storage initialization; no source
checkout or local build is required. It supports the same settings as local
Compose, including the optional cookies override.

To deploy a specific commit or digest, set `VESPERTAPE_IMAGE` in `.env`:

```dotenv
VESPERTAPE_IMAGE=ghcr.io/khawarmehfooz/vespertape:sha-<full-commit>
```

Before upgrading, stop the app and back up its data volume, including SQLite
WAL files, and the downloads directory. Then:

```sh
docker compose -f docker-compose.image.yml stop vespertape
docker compose -f docker-compose.image.yml pull
docker compose -f docker-compose.image.yml up -d
```

Stopping before storage initialization prevents ownership changes while the
worker is writing files. Restore the data backup when reverting a version that
changed the database schema. Do not use `down -v` unless you intend to delete
persistent data. See [security and deployment](deployment.md) before exposing
the app beyond localhost.

## References

- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Docker GitHub Actions caching](https://docs.docker.com/build/ci/github-actions/cache/)
- [Docker SBOM and provenance](https://docs.docker.com/build/ci/github-actions/attestations/)
