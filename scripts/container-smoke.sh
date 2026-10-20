#!/usr/bin/env bash
# Starts the deployment's containers and uses them, rather than only building
# them (DECISIONS §49). A Dockerfile can build and still ship an image that does
# not work: the service image copies chosen files out of its build stage, and
# the native extension and TreeDiff are each allowed to fail without failing
# the build. This finds that here instead of on the VM.
#
#   scripts/container-smoke.sh              # build, start, check, remove
#   scripts/container-smoke.sh --no-build   # use images already built
#
# Runs under its own compose project, on its own ports and its own volume, so a
# local stack is left alone; `down -v` removes all of it afterwards. The checks
# themselves are scripts/container_smoke.py.
set -euo pipefail

cd "$(dirname "$0")/.."

build=(--build)
if [ "${1:-}" = "--no-build" ]; then
  build=()
elif [ $# -gt 0 ]; then
  echo "usage: $0 [--no-build]" >&2
  exit 2
fi

export COMPOSE_PROJECT_NAME=phylodelta-smoke
export PHYLODELTA_PORT="${SMOKE_API_PORT:-18001}"
export PHYLODELTA_WEB_PORT="${SMOKE_WEB_PORT:-13001}"
compose() {
  docker compose -f docker-compose.yml -f scripts/container-smoke.compose.yml "$@"
}

finish() {
  status=$?
  if [ "$status" -ne 0 ]; then
    echo "--- container logs (the smoke test failed) ---" >&2
    compose logs --no-color --tail 200 >&2 || true
  fi
  compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  exit "$status"
}
trap finish EXIT

# --wait returns once every service is running and the API's healthcheck
# passes, or fails if one exits or never becomes healthy.
# (The `+` form: an empty array is "unbound" to set -u in macOS's bash 3.2.)
compose up --detach --wait --wait-timeout 180 ${build[@]+"${build[@]}"}

# The native extension is optional in the image (Dockerfile) and the code falls
# back to Python without saying so, so ask each process that loads it. The
# worker is the one that matters: it runs the parser and the correspondence
# search.
for service in phylodelta-service phylodelta-worker; do
  compose exec -T "$service" python -c '
import sys
from phylodelta.trees import native
sys.exit(0 if native.available() else "the native extension did not load")
' || { echo "✗ $service: the native extension is not loaded; the image runs on the Python fallback" >&2; exit 1; }
  echo "✓ $service loads the native extension"
done

python3 scripts/container_smoke.py \
  --api "http://127.0.0.1:${PHYLODELTA_PORT}" \
  --web "http://127.0.0.1:${PHYLODELTA_WEB_PORT}" \
  --version "$(tr -d '[:space:]' < VERSION)"
