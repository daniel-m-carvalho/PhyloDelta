#!/usr/bin/env python3
"""One release version for the whole repository (DECISIONS §48).

`VERSION` at the repository root is the release; every manifest that carries a
version must say the same. The library, the web app, the benchmark harness and
the server are developed and tested together, so separate versions would only
let them drift: a bug report naming "0.3.0" should name one state of all four.

    python3 scripts/version.py            # check: exit 1, naming each file that disagrees
    python3 scripts/version.py set 0.2.0  # write VERSION and every manifest

The lockfiles are written too: npm and uv record each workspace's own version,
and a lockfile that disagrees with its manifest makes `npm ci` / `uv sync
--frozen` either rewrite it or refuse.

Standard library only, so CI can run it before anything is installed. Edits
are textual, not parse-and-dump: dumping would reformat the files, and a
version bump should be a diff of version lines.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"

#: X.Y.Z, optionally with a pre-release such as 0.2.0-rc.1. No build metadata:
#: npm drops it, so it could not mean the same thing in every manifest.
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?$")

#: The npm workspaces whose package.json carries the release.
NPM_PACKAGES = ("lib", "web", "bench")


def _package_json(path: Path):
    """A package.json's top-level "version" line: read and replace."""

    pattern = re.compile(r'^(  "version": ")([^"]*)(")', re.MULTILINE)

    def read() -> str | None:
        found = pattern.search(path.read_text())
        return found.group(2) if found else None

    def write(version: str) -> None:
        text = path.read_text()
        if not pattern.search(text):
            raise SystemExit(f"{path.relative_to(ROOT)} has no top-level version to set")
        path.write_text(pattern.sub(rf"\g<1>{version}\g<3>", text, count=1))

    return read, write


def _package_lock(workspace: str):
    """The workspace's entry in code/package-lock.json (`packages["lib"]`, …)."""
    path = ROOT / "code" / "package-lock.json"
    # The entry's opening line, then its "version" before the next entry: a
    # workspace entry is `"lib": {` at four spaces, its fields at six.
    pattern = re.compile(
        rf'(^    "{re.escape(workspace)}": \{{\n(?:      .*\n)*?      "version": ")([^"]*)(")',
        re.MULTILINE,
    )

    def read() -> str | None:
        return json.loads(path.read_text())["packages"].get(workspace, {}).get("version")

    def write(version: str) -> None:
        text = path.read_text()
        if not pattern.search(text):
            raise SystemExit(f"code/package-lock.json has no version for workspace {workspace!r}")
        path.write_text(pattern.sub(rf"\g<1>{version}\g<3>", text, count=1))

    return read, write


def _toml_version(path: Path, after: str):
    """The `version = "…"` line following `after` (a section or a package name)."""
    pattern = re.compile(rf'({re.escape(after)}\n(?:.*\n)*?version = ")([^"]*)(")')

    def read() -> str | None:
        found = pattern.search(path.read_text())
        return found.group(2) if found else None

    def write(version: str) -> None:
        text = path.read_text()
        if not pattern.search(text):
            raise SystemExit(f"{path.relative_to(ROOT)} has no version after {after!r}")
        path.write_text(pattern.sub(rf"\g<1>{version}\g<3>", text, count=1))

    return read, write


def places() -> dict[str, tuple]:
    """Every file that carries the release, by the name a mismatch is reported under."""
    found = {}
    for workspace in NPM_PACKAGES:
        found[f"code/{workspace}/package.json"] = _package_json(ROOT / "code" / workspace / "package.json")
        found[f"code/package-lock.json ({workspace})"] = _package_lock(workspace)
    server = ROOT / "code" / "server"
    found["code/server/pyproject.toml"] = _toml_version(server / "pyproject.toml", "[project]")
    found["code/server/uv.lock (phylodelta)"] = _toml_version(server / "uv.lock", 'name = "phylodelta"')
    return found


def release() -> str:
    version = VERSION_FILE.read_text().strip()
    if not SEMVER.match(version):
        raise SystemExit(f"VERSION holds {version!r}, which is not a version like 0.1.0")
    return version


def check() -> int:
    version = release()
    wrong = [(name, read()) for name, (read, _) in places().items() if read() != version]
    for name, found in wrong:
        print(f"{name} says {found!r}; VERSION says {version!r}", file=sys.stderr)
    if wrong:
        print(f"run: python3 scripts/version.py set {version}", file=sys.stderr)
        return 1
    print(version)
    return 0


def set_version(version: str) -> int:
    if not SEMVER.match(version):
        raise SystemExit(f"{version!r} is not a version like 0.1.0")
    VERSION_FILE.write_text(version + "\n")
    for _, write in places().values():
        write(version)
    return check()


def main(argv: list[str]) -> int:
    if not argv:
        return check()
    if len(argv) == 2 and argv[0] == "set":
        return set_version(argv[1])
    print(__doc__.split("\n\n")[2], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
