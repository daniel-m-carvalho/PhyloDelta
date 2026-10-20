# PhyloDelta

[![CI](https://github.com/daniel-m-carvalho/PhyloDelta/actions/workflows/ci.yml/badge.svg)](https://github.com/daniel-m-carvalho/PhyloDelta/actions/workflows/ci.yml)

**Compare two large phylogenetic trees side by side in the browser.** That includes trees with
hundreds of thousands of leaves, which tools that load whole trees (such as phylo.io) cannot open.

PhyloDelta never sends a whole tree to the browser. The server stores each tree and its comparison
once, and for every view sends only a summary sized to the screen: the largest groups of leaves
folded into triangles, each part coloured by how much the two trees agree. Opening a group asks for
the next level of detail. Part of a master's thesis; to be integrated into PHYLOViZ.

## Documentation

| | |
|---|---|
| **[Using the web app](docs/web-app-guide.md)** | Upload trees, open a comparison, navigate, search, isolate data, export. With a video for each task. |
| **[Reading a comparison](docs/reading-a-comparison.md)** | What every colour, shape and mark on the comparison screen means. |
| **[Integrating the API](docs/api-integration.md)** | For developers: authentication, upload → poll → view, every endpoint with real examples. |
| **[Design record](docs/DECISIONS.md)** | Why it is built this way: each decision with the alternatives weighed and the measurements that settled it. |

Component references: the [server](code/server/README.md), the
[rendering library](code/lib/README.md) and the [deployment](deploy/README.md).

## Run it

**With Docker** (the simplest), from the repository root:

```bash
docker compose up -d --build
```

Then open <http://localhost:3001>. The API is on <http://localhost:8001> (reference at
[`/docs`](http://localhost:8001/docs)). On first start the demo comparisons (*Vibrio* and
*Clostridium*) are built automatically, which takes a few minutes.

**For development**, in three terminals (needs Python 3.12 with [uv](https://docs.astral.sh/uv/),
and Node 20.19+ or 22.12+):

```bash
cd code/server && uv sync && uv run phylodelta build-all             # once: builds the demo data
cd code/server && uv run uvicorn phylodelta.api.app:app --reload     # API on :8000
cd code/server && uv run phylodelta worker                           # computes uploaded comparisons
cd code && npm install && npm start                                  # web app on :5173
```

## Repository

| Path | |
|---|---|
| `code/server/` | The API and the worker: FastAPI, Python 3.12. Trees in a columnar store, comparison metrics as plugins, an optional C++ extension for speed. |
| `code/web/` | The web app: React + Vite. |
| `code/lib/` | `phylo-tree-viewer`, the rendering library the web app is built on (Sigma.js, WebGL). Backend-agnostic: it never fetches. |
| `code/bench/` | The benchmark harness and its results (`results/TABLES.md`). |
| `datasets/` | The demo trees (Newick) and isolate data (EnteroBase exports). |
| `deploy/` | Notes for running it on a server. |
| `docs/` | The guides above and the design record. |

`code/` is an npm workspace: install once there for the library, the web app and the benchmarks.

## Tests

```bash
cd code/server && uv run pytest -q    # server
cd code && npm test                   # library and web app
scripts/container-smoke.sh            # the Docker deployment, started and used
```

CI runs all of these on every pull request, with the linters (ruff, oxlint) and the checks in
`.pre-commit-config.yaml`. To have git run the same checks before each commit, and the suites
before each push, install the hooks once per clone:

```bash
uvx pre-commit install
```

## License

[MIT](LICENSE).
