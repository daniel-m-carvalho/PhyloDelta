"""scripts/version.py, run against a copy of the repository's real manifests (§48).

A copy, not fixtures: the script edits by regular expression, and what has to
keep working is those expressions against the files as they really are —
npm's lockfile layout, uv's, the top-level "version" of each package.json and
not a dependency's.

Standard library only, like the script, so CI runs it before installing
anything:

    python3 -m unittest discover scripts/tests
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import version  # noqa: E402  (found through the path set above)

#: Every file the script reads or writes, relative to the repository root.
FILES = [
    "VERSION",
    "code/package-lock.json",
    "code/server/pyproject.toml",
    "code/server/uv.lock",
    *(f"code/{workspace}/package.json" for workspace in version.NPM_PACKAGES),
]


class VersionScript(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="version-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        for name in FILES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        # The module resolves every path from these two at call time.
        self._saved = version.ROOT, version.VERSION_FILE
        version.ROOT, version.VERSION_FILE = self.root, self.root / "VERSION"
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        version.ROOT, version.VERSION_FILE = self._saved

    def run_main(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = version.main(list(argv))
            except SystemExit as refused:
                code = refused.code if isinstance(refused.code, int) else 1
                err.write(str(refused.code))
        return code, out.getvalue(), err.getvalue()

    def read(self, name: str) -> str:
        return (self.root / name).read_text()

    # --- the state the repository is committed in ----------------------------

    def test_the_repository_agrees_with_itself(self) -> None:
        code, out, err = self.run_main()
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), self.read("VERSION").strip())

    # --- set -----------------------------------------------------------------

    def test_set_writes_every_place_and_check_then_passes(self) -> None:
        code, _, err = self.run_main("set", "9.8.7-rc.1")
        self.assertEqual(code, 0, err)
        # Read back by parsing, not by the script's own expressions: a regex
        # that matched the wrong line would agree with itself.
        self.assertEqual(self.read("VERSION"), "9.8.7-rc.1\n")
        lock = json.loads(self.read("code/package-lock.json"))
        for workspace in version.NPM_PACKAGES:
            manifest = json.loads(self.read(f"code/{workspace}/package.json"))
            self.assertEqual(manifest["version"], "9.8.7-rc.1", workspace)
            self.assertEqual(lock["packages"][workspace]["version"], "9.8.7-rc.1", workspace)
        self.assertEqual(
            tomllib.loads(self.read("code/server/pyproject.toml"))["project"]["version"],
            "9.8.7-rc.1",
        )
        packages = tomllib.loads(self.read("code/server/uv.lock"))["package"]
        (ours,) = [p for p in packages if p["name"] == "phylodelta"]
        self.assertEqual(ours["version"], "9.8.7-rc.1")

    def test_set_changes_only_version_lines(self) -> None:
        before = {name: self.read(name) for name in FILES}
        self.run_main("set", "9.8.7")
        # One line per file, except the npm lock: one per workspace entry.
        expected = {"code/package-lock.json": len(version.NPM_PACKAGES)}
        for name in FILES:
            old, new = before[name].splitlines(), self.read(name).splitlines()
            self.assertEqual(len(old), len(new), name)
            changed = [(a, b) for a, b in zip(old, new, strict=True) if a != b]
            self.assertEqual(len(changed), expected.get(name, 1), f"{name}: {changed}")
            for _, line in changed:
                self.assertIn("9.8.7", line, name)

    def test_set_leaves_dependency_versions_alone(self) -> None:
        # The lockfile has hundreds of "version" lines; only the workspace
        # entries are ours. The root entry of the lock ("") must stay too.
        lock_before = json.loads(self.read("code/package-lock.json"))
        self.run_main("set", "9.8.7")
        lock_after = json.loads(self.read("code/package-lock.json"))
        for path, entry in lock_before["packages"].items():
            if path in version.NPM_PACKAGES:
                continue
            self.assertEqual(entry.get("version"), lock_after["packages"][path].get("version"), path)

    def test_set_refuses_what_is_not_a_version_and_writes_nothing(self) -> None:
        before = {name: self.read(name) for name in FILES}
        for bad in ("1.2", "v1.2.3", "01.2.3", "1.2.3+build.5", "1.2.3 "):
            code, _, err = self.run_main("set", bad)
            self.assertNotEqual(code, 0, bad)
            self.assertIn("not a version", err, bad)
        self.assertEqual(before, {name: self.read(name) for name in FILES})

    # --- check ---------------------------------------------------------------

    def test_check_names_each_file_that_disagrees(self) -> None:
        path = self.root / "code/web/package.json"
        path.write_text(path.read_text().replace('"version": "', '"version": "7.7.7-', 1))
        uv_lock = self.root / "code/server/uv.lock"
        text = uv_lock.read_text()
        uv_lock.write_text(text.replace('name = "phylodelta"\nversion = "', 'name = "phylodelta"\nversion = "7.', 1))

        code, out, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("code/web/package.json says", err)
        self.assertIn("code/server/uv.lock (phylodelta) says", err)
        self.assertNotIn("code/lib/package.json", err)
        self.assertIn("run: python3 scripts/version.py set", err)

    def test_check_refuses_a_version_file_that_is_not_a_version(self) -> None:
        (self.root / "VERSION").write_text("next\n")
        code, _, err = self.run_main()
        self.assertNotEqual(code, 0)
        self.assertIn("'next'", err)

    def test_an_unknown_command_prints_usage(self) -> None:
        code, _, err = self.run_main("bump")
        self.assertEqual(code, 2)
        self.assertIn("scripts/version.py set", err)


class AsAProgram(unittest.TestCase):
    """The exit code is what CI acts on, so check it through a real process."""

    def test_exit_code_of_the_check(self) -> None:
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "version.py")],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
