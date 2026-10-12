#!/usr/bin/env bash
# Verify the built artifact with its normal non-root user, entrypoint and storage.
set -euo pipefail
image="${1:?Usage: smoke_image.sh IMAGE}"
container="vespertape-smoke-${RANDOM}-${RANDOM}"
cleanup() {
  docker logs "$container" || true
  docker rm -fv "$container" >/dev/null || true
}
trap cleanup EXIT
docker run -d --name "$container" --init --cap-drop ALL \
  --security-opt no-new-privileges "$image" >/dev/null
for attempt in $(seq 1 45); do
  status="$(docker inspect --format '{{.State.Health.Status}}' "$container")"
  if [ "$status" = healthy ]; then
    docker exec "$container" python -c '
import os, re, shutil, urllib.request
assert os.getuid() != 0
assert all(shutil.which(tool) for tool in ("node", "ffmpeg", "ffprobe"))
base = "http://127.0.0.1:8000"
html = urllib.request.urlopen(base + "/").read().decode()
assets = re.findall(r"(?:src|href)=\"(/assets/[^\"]+)\"", html)
assert assets, "Built frontend assets missing"
for asset in assets:
    assert urllib.request.urlopen(base + asset).status == 200
'
    exit 0
  fi
  if [ "$(docker inspect --format '{{.State.Running}}' "$container")" != true ]; then
    exit 1
  fi
  sleep 2
done
echo 'Container did not become healthy' >&2
exit 1
