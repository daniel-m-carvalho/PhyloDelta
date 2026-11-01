"""The Environment block, read from the machine, and the refusal to measure.

`start` runs before anything is measured and stops the campaign unless this is a
clean checkout of the tag `v<VERSION>`. Table 23 went out on "b31de35 + uncommitted
changes", and a commit that names code nobody can check out is not a provenance.
Everything a table says about how it was made is recorded here, so the tables can
be regenerated later, from any checkout, and still name the commit that measured
them.

`finish` reads it all again and refuses if anything moved during the run. Chrome
updates itself, and a campaign that spans an update is two campaigns.

    uv run --project ../server python harness/campaign_env.py start
    uv run --project ../server python harness/campaign_env.py finish

`CAMPAIGN_DRY_RUN=1` allows a dirty tree and a missing tag, marks the file, and
exists only to rehearse the chain on the small rungs.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1]
REPO = BENCH.parents[1]
OUT = BENCH / "results" / "environment.json"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
#: What the campaign writes. Everything else in the tree must match the commit.
OUTPUTS = "code/bench/results/"
DRY = os.environ.get("CAMPAIGN_DRY_RUN") == "1"


def run(*command: str, cwd: Path = REPO) -> str:
    return subprocess.run(
        command, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def refuse(why: str) -> None:
    raise SystemExit(f"\nREFUSING TO MEASURE: {why}\n")


def dirty() -> list[str]:
    lines = run("git", "status", "--porcelain").splitlines()
    return [line for line in lines if OUTPUTS not in line]


def tree_sha256(root: Path) -> str:
    """One hash over every file of the published `dist/`: "unmodified" as a fact."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def browser_flags() -> list[str]:
    """Read from the file that launches the browser, not restated beside it."""
    source = (BENCH / "harness" / "browser.mjs").read_text()
    return re.findall(r'^\s*"(--[^"]+)",', source, re.M)


def store_volume(path: str) -> dict:
    device = run("df", path).splitlines()[1].split()[0]
    info = run("diskutil", "info", device)
    wanted = {"Solid State": "solid_state", "File System Personality": "file_system"}
    found = {}
    for line in info.splitlines():
        key, _, value = line.partition(":")
        if key.strip() in wanted:
            found[wanted[key.strip()]] = value.strip()
    return found


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        refuse(f"{name} is not set")
    return value


def observed() -> dict:
    """Everything that must be the same at the start and at the end."""
    home = Path(required("PHYLOIO_HOME"))
    if not (home / "dist").is_dir():
        refuse(f"PHYLOIO_HOME={home} has no dist/")
    package = json.loads((home / "package.json").read_text())
    playwright = json.loads((REPO / "code/node_modules/playwright/package.json").read_text())
    commit = run("git", "rev-parse", "HEAD")
    tag = run("git", "tag", "--points-at", "HEAD") or None
    store = required("CAMPAIGN_ROOT")
    return {
        "commit": commit,
        "commit_short": commit[:7],
        "tag": tag,
        "machine": {
            "chip": run("sysctl", "-n", "machdep.cpu.brand_string"),
            "memory_gib": int(run("sysctl", "-n", "hw.memsize")) // 2**30,
            "performance_cores": int(run("sysctl", "-n", "hw.perflevel0.physicalcpu")),
            "efficiency_cores": int(run("sysctl", "-n", "hw.perflevel1.physicalcpu")),
        },
        "os": {
            "product": run("sw_vers", "-productVersion"),
            "build": run("sw_vers", "-buildVersion"),
            "kernel": run("uname", "-r"),
        },
        "browser": run(CHROME, "--version").replace("Google ", ""),
        "browser_flags": browser_flags(),
        "runtimes": {
            "python": platform.python_version(),
            "node": run("node", "--version").removeprefix("v"),
            "playwright": playwright["version"],
            "uv": run("uv", "--version").split()[1],
        },
        "phyloio": {
            "name": package["name"],
            "version": package["version"],
            "home": str(home),
            "dist_sha256": tree_sha256(home / "dist"),
        },
        "settings": {
            "PHYLODELTA_THREADS": required("PHYLODELTA_THREADS"),
            "PHYLODELTA_METRIC_MEMORY": required("PHYLODELTA_METRIC_MEMORY"),
        },
        "store": {"root": store, **store_volume(store)},
    }


def start() -> None:
    changed = dirty()
    tag = run("git", "tag", "--points-at", "HEAD")
    wanted = f"v{(REPO / 'VERSION').read_text().strip()}"
    if changed and not DRY:
        refuse("the tree is dirty:\n  " + "\n  ".join(changed))
    if wanted not in tag.split() and not DRY:
        refuse(f"HEAD is not the tag {wanted} (tags here: {tag or 'none'})")

    values = observed()
    if values["settings"]["PHYLODELTA_THREADS"] != "2":
        refuse("the deployment setting is PHYLODELTA_THREADS=2")
    OUT.write_text(json.dumps({
        **values,
        "dry_run": DRY,
        "started": datetime.now(UTC).isoformat(timespec="seconds"),
        "power_at_start": run("pmset", "-g", "batt").splitlines()[0],
    }, indent=1) + "\n")
    print(f"environment recorded: {values['commit_short']} {values['tag']} "
          f"{values['browser']} phylo.io {values['phyloio']['version']}")


def finish() -> None:
    recorded = json.loads(OUT.read_text())
    now = observed()
    moved = [key for key, value in now.items() if recorded.get(key) != value]
    if dirty() and not recorded["dry_run"]:
        moved.append("tree: " + "; ".join(dirty()))
    recorded["finished"] = datetime.now(UTC).isoformat(timespec="seconds")
    recorded["power_at_finish"] = run("pmset", "-g", "batt").splitlines()[0]
    recorded["moved_during_run"] = moved
    OUT.write_text(json.dumps(recorded, indent=1) + "\n")
    if moved:
        refuse(f"the environment changed during the run: {', '.join(moved)}")
    print("environment unchanged across the run")


if __name__ == "__main__":
    {"start": start, "finish": finish}[sys.argv[1]]()
