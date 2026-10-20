#!/usr/bin/env python3
"""The checks scripts/container-smoke.sh runs against a started stack (§49).

    python3 scripts/container_smoke.py --api URL --web URL --version X.Y.Z

Against the API directly: it answers, is the release in VERSION, and every
metric it lists can run (TreeDiff's two are built into the image or not, and
the build does not fail when they are not).

Against the web container: nginx serves the app and its assets, falls back to
the app for a client route, refuses an unknown API path as JSON rather than
answering with the page, and proxies /api/v1/ to the service.

Then a comparison all the way through the proxy, as a browser would make one:
upload two six-leaf trees and an isolate table, let the worker compute every
metric, read a slice, delete it. That is the one check that needs the API, the
worker, the shared volume and the proxy all to be right at once.

Standard library only: CI runs it with the system Python.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

LEFT = b"(((a:0.1,b:0.1):0.2,(c:0.1,d:0.1):0.2):0.1,(e:0.1,f:0.1):0.3);"
RIGHT = b"(((a:0.1,c:0.1):0.2,(b:0.1,d:0.1):0.2):0.1,(e:0.1,f:0.1):0.3);"
# Keyed by a column that is not the default `ST`, so the key choice (§47) is
# exercised too; one row names no leaf, and must be reported as such.
ISOLATES = b"Name\tcountry\na\tPT\nb\tPT\nc\tES\nd\tES\ne\tFR\nf\tFR\nzz\tFR\n"

failures: list[str] = []


def check(label: str, ok: bool, detail: object = "") -> bool:
    print(f"{'✓' if ok else '✗'} {label}" + ("" if ok or detail == "" else f" — {detail}"))
    if not ok:
        failures.append(label)
    return ok


def call(url: str, *, method="GET", data=None, headers=None, timeout=30):
    """(status, headers, body bytes). Never raises for an HTTP error status."""
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as failed:
        return failed.code, failed.headers, failed.read()


def call_json(url: str, **kwargs):
    status, _, raw = call(url, **kwargs)
    try:
        return status, json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return status, {"not json": raw[:200].decode("utf-8", "replace")}


def multipart(files: dict[str, tuple[str, bytes]], form: dict[str, str]):
    boundary = f"----smoke{uuid.uuid4().hex}"
    body = io.BytesIO()
    for name, value in form.items():
        body.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
                   f"{value}\r\n".encode())
    for name, (filename, content) in files.items():
        body.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                   f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
        body.write(content + b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())
    return body.getvalue(), {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def the_api(api: str, version: str) -> list[str]:
    """Checks the service on its own port; returns the metric names it offers."""
    status, health = call_json(f"{api}/api/v1/health")
    check("the API answers /health", status == 200 and health.get("status") == "ok", health)
    check(f"it is release {version}", (health or {}).get("version") == version,
          f"/health says version {(health or {}).get('version')!r}")
    check("it reports its API contract version", bool((health or {}).get("api_version")), health)

    status, metrics = call_json(f"{api}/api/v1/metrics")
    if not check("it lists its metrics", status == 200 and bool(metrics), metrics):
        return []
    missing = [m["name"] for m in metrics if not m["available"]]
    # Refused by name: TreeDiff's metrics are the ones that can go missing
    # while the image still builds (Dockerfile).
    check("every metric it lists can run", not missing,
          f"unavailable: {', '.join(missing)} (TreeDiff not built into the image?)")
    return [m["name"] for m in metrics if m["available"]]


def the_web_container(web: str, version: str) -> None:
    status, headers, page = call(f"{web}/")
    html = page.decode("utf-8", "replace")
    check("nginx serves the app", status == 200 and 'id="root"' in html, f"HTTP {status}")
    check("index.html is not cached", "no-cache" in (headers.get("Cache-Control") or ""),
          headers.get("Cache-Control"))

    assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
    if check("the page references its built assets", bool(assets), html[:200]):
        status, headers, _ = call(f"{web}{assets[0]}")
        # Two headers, not one: nginx's `expires` writes max-age and the
        # config adds `public, immutable` beside it.
        cache = ", ".join(headers.get_all("Cache-Control") or [])
        check(f"and they are served, cached for good ({assets[0]})",
              status == 200 and "immutable" in cache and "max-age=31536000" in cache,
              f"HTTP {status}, Cache-Control {cache!r}")

    status, _, page = call(f"{web}/some/client/route")
    check("a client route falls back to the app", status == 200 and b'id="root"' in page, f"HTTP {status}")

    status, body = call_json(f"{web}/api/v2/health")
    check("an unknown API path is a JSON 404, not the page",
          status == 404 and isinstance(body, dict) and body.get("code") == "not_found",
          f"HTTP {status}: {body}")

    status, health = call_json(f"{web}/api/v1/health")
    check("nginx proxies /api/v1/ to the service",
          status == 200 and (health or {}).get("version") == version, f"HTTP {status}: {health}")


def a_comparison_through_the_proxy(web: str, metrics: list[str]) -> None:
    base = f"{web}/api/v1"
    body, headers = multipart(
        {"left_tree": ("left.nwk", LEFT), "right_tree": ("right.nwk", RIGHT),
         "left_isolates": ("isolates.tsv", ISOLATES)},
        {"name": f"smoke-{uuid.uuid4().hex[:8]}", "metrics": ",".join(metrics),
         "left_isolates_key": "Name", "isolates_shared": "true"},
    )
    status, accepted = call_json(f"{base}/comparisons", method="POST", data=body, headers=headers)
    if not check("an upload through the proxy is accepted", status == 202, f"HTTP {status}: {accepted}"):
        return
    pair = accepted["id"]

    # The worker is the only thing that moves it on, so this also says the
    # worker is up, claims jobs and writes where the API reads.
    deadline, record = time.monotonic() + 180, {}
    while time.monotonic() < deadline:
        _, record = call_json(f"{base}/comparisons/{pair}/status")
        if record.get("status") in {"ready", "failed"}:
            break
        time.sleep(1)
    if not check("the worker computes it", record.get("status") == "ready",
                 f"{record.get('status')}: {record.get('error')}"):
        return
    check("every metric asked for was computed",
          sorted(record.get("metrics_ready", [])) == sorted(metrics),
          f"ready {record.get('metrics_ready')}, failed {record.get('metrics_failed')}")
    report = record.get("isolates", {}).get("left", {})
    check("the isolate table joined on its key column",
          report.get("key_column") == "Name" and report.get("rows_unmatched") == 1
          and report.get("leaves_without_rows") == 0 and not report.get("error"),
          report)

    _, summary = call_json(f"{base}/comparisons/{pair}")
    status, sliced = call_json(f"{base}/trees/{summary['left']}/slice?compare={pair}&budget=10")
    check("its trees slice, with all six leaves",
          status == 200 and sliced.get("total_leaves") == 6, f"HTTP {status}: {str(sliced)[:200]}")

    status, _ = call_json(f"{base}/comparisons/{pair}", method="DELETE")
    gone, _ = call_json(f"{base}/comparisons/{pair}/status")
    check("and it can be deleted", status == 200 and gone == 404, f"delete {status}, then status {gone}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", required=True, help="the service, e.g. http://127.0.0.1:18001")
    parser.add_argument("--web", required=True, help="the web container, e.g. http://127.0.0.1:13001")
    parser.add_argument("--version", required=True, help="the release the images must report")
    args = parser.parse_args()

    metrics = the_api(args.api.rstrip("/"), args.version)
    the_web_container(args.web.rstrip("/"), args.version)
    if metrics:
        a_comparison_through_the_proxy(args.web.rstrip("/"), metrics)

    if failures:
        print(f"\n{len(failures)} check(s) failed", file=sys.stderr)
        return 1
    print("\ncontainer smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
