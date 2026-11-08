#!/usr/bin/env bash
#
# The whole evaluation, from a fresh clone of the release tag (§34.20).
#
#   PHYLOIO_HOME=<phyloio-2.2.5> code/bench/harness/run_campaign.sh <root> [step ...]
#
# <root> holds the stores, logs and step stamps, on an SSD and outside the clone.
# With no steps it runs all of them in order; a finished step is stamped and
# skipped, so an interrupted run resumes where it stopped. Stop at the first
# failure: a result that followed a failure is not a result.
#
# It starts its own API and worker for each store, and reads thread counts back
# from what each build reports (tools/bench_build.py).
#
# CAMPAIGN_DRY_RUN=1 with CAMPAIGN_RUNGS="1000 2500" rehearses the chain.

set -euo pipefail

if [ -z "${CAMPAIGN_CAFFEINATED:-}" ]; then
  # The laptop suspends after a minute on battery, and a `sleep 1200` in a chained
  # run once took 58 minutes (§34.11b).
  CAMPAIGN_CAFFEINATED=1 exec caffeinate -dimsu "$0" "$@"
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH="$(dirname "$HERE")"
CODE="$(dirname "$BENCH")"
SERVER="$CODE/server"
RESULTS="$BENCH/results"

: "${PHYLOIO_HOME:?set PHYLOIO_HOME to the phylo.io release under test}"
export PHYLOIO_HOME
CAMPAIGN_ROOT="$(cd "${1:?usage: run_campaign.sh <root> [step ...]}" && pwd)"
export CAMPAIGN_ROOT
shift
export PHYLODELTA_THREADS=2
#: Explicit, recorded, and the campaign's own: the code has no default (§50). On
#: this 24 GiB machine MAST runs to 35,290 leaves and is declined above.
export PHYLODELTA_METRIC_MEMORY="${PHYLODELTA_METRIC_MEMORY:-16G}"

LADDER="$BENCH/trees/ladder"
RUNGS="${CAMPAIGN_RUNGS:-1000 2500 5000 10000 17645 35290 70580 141160 282320 564640}"
API_PORT=8010
export PHYLODELTA_BENCH_API_PORT="$API_PORT"
API="http://127.0.0.1:$API_PORT/api/v1"
PY="$SERVER/.venv/bin/python"
BACKEND_PIDS=()

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }

# ---------------------------------------------------------------- the backend

backend_up() {  # store threads worker-log
  local store="$1" threads="$2" worker_log="$3"
  mkdir -p "$store"
  # The venv's own entry points, not `uv run`: the worker's pid has to be the
  # process doing the work, because its RSS is what Table 11 samples.
  PHYLODELTA_STORE="$store" PHYLODELTA_THREADS="$threads" \
    "$SERVER/.venv/bin/uvicorn" phylodelta.api.app:app --port "$API_PORT" --log-level warning \
    >>"$CAMPAIGN_ROOT/logs/api.log" 2>&1 &
  BACKEND_PIDS+=($!)
  PHYLODELTA_STORE="$store" PHYLODELTA_THREADS="$threads" \
    "$SERVER/.venv/bin/phylodelta" worker >>"$worker_log" 2>&1 &
  WORKER_PID=$!
  BACKEND_PIDS+=("$WORKER_PID")
  for _ in $(seq 1 120); do
    curl -fs "$API/health" >/dev/null 2>&1 && break
    sleep 0.5
  done
  curl -fs "$API/health" >/dev/null
  # Every metric, on this build, or nothing is measured. A missing TreeDiff turns
  # into "available: false" and a table that quietly lacks a column.
  curl -fs "$API/metrics" | "$PY" -c '
import json, sys
missing = [m["name"] for m in json.load(sys.stdin) if not m["available"]]
sys.exit(f"metrics unavailable: {missing}" if missing else 0)'
}

backend_down() {
  [ ${#BACKEND_PIDS[@]} -eq 0 ] && return 0
  kill "${BACKEND_PIDS[@]}" 2>/dev/null || true
  wait "${BACKEND_PIDS[@]}" 2>/dev/null || true
  BACKEND_PIDS=()
  sleep 2
}
trap backend_down EXIT

pair_of() {  # leaves [build-file]
  "$PY" -c '
import json, sys
rows = json.load(open(sys.argv[1]))
print(next(r["id"] for r in rows if r["leaves"] == int(sys.argv[2])))' \
    "$RESULTS/${2:-server_build.json}" "$1"
}

# ------------------------------------------------------------------- the steps

step_setup() {
  # Everything a fresh clone lacks, from the lockfiles and the pinned recipes.
  (cd "$SERVER" && uv sync --frozen --python 3.12 && ./native/build.sh && ./native/build_treediff.sh \
    && ./native/build_rspr.sh)
  (cd "$CODE" && npm ci --cache "$CAMPAIGN_ROOT/npm-cache" && npm run build --workspace web)
}

step_env() {
  # Inputs that remain from an earlier campaign must not be able to fill a table
  # that this run failed to produce. 2.1.1's probe stays: it is the one figure
  # that is about another release and cannot be re-measured against this one.
  find "$RESULTS" -type f \( -name '*.json' -o -name '*.jsonl' \) \
    ! -name 'phyloio_bcn_2.1.1.json' -delete
  (cd "$BENCH" && "$PY" harness/campaign_env.py start)
}

step_ladder() {
  rm -rf "$LADDER"
  # shellcheck disable=SC2086
  (cd "$SERVER" && "$PY" tools/make_ladder.py "$LADDER" $RUNGS)
  (cd "$SERVER" && "$PY" tools/ladder_stats.py "$LADDER" "$RESULTS/ladder_stats.json")
  (cd "$SERVER" && "$PY" tools/prepare_rf_input.py \
    "$CODE/../datasets/gen_trees/vibrio-nj-tree.nwk" \
    "$CODE/../datasets/gen_trees/vibrio-upgma-tree.nwk" "$BENCH/trees/vibrio")
}

# Thread builds first, from an idle machine, one store each (§34.8).
thread_build() {  # threads [metrics]
  local threads="$1" metrics="${2:-}"
  backend_up "$CAMPAIGN_ROOT/stores/thr$threads${metrics:+-app}" "$threads" \
    "$CAMPAIGN_ROOT/logs/worker-thr$threads.log"
  (cd "$SERVER" && "$PY" tools/measure_thread_builds.py "$LADDER" "$API" "$threads" ${metrics:+"$metrics"})
  backend_down
}
step_threads_1() { thread_build 1; }
step_threads_2() { thread_build 2; }
step_threads_10() { thread_build 10; }
#: Table 8(b): what UploadPanel sends by default, the distance and "also moved".
step_threads_2_app() { thread_build 2 rf,mast; }

step_store_rf() {
  backend_up "$CAMPAIGN_ROOT/stores/bench" 2 "$CAMPAIGN_ROOT/logs/worker-bench.log"
  (cd "$SERVER" && "$PY" tools/build_ladder_stores.py "$LADDER" "$API")
  backend_down
}

step_store_app() {
  backend_up "$CAMPAIGN_ROOT/stores/app" 2 "$CAMPAIGN_ROOT/logs/worker-app.log"
  (cd "$SERVER" && BENCH_METRICS=rf,mast BENCH_BUILD_FILE=server_build_app.json \
    "$PY" tools/build_ladder_stores.py "$LADDER" "$API")
  backend_down
}

memory() {  # threads
  backend_up "$CAMPAIGN_ROOT/stores/mem$1" "$1" "$CAMPAIGN_ROOT/logs/worker-mem$1.log"
  (cd "$SERVER" && "$PY" tools/measure_build_memory.py "$LADDER" "$API" "$WORKER_PID" "$1")
  backend_down
}
step_memory_2() { memory 2; }
step_memory_10() { memory 10; }

step_metric_builds() {
  local log_file="$CAMPAIGN_ROOT/logs/worker-metrics.log"
  : >"$log_file"
  backend_up "$CAMPAIGN_ROOT/stores/metrics" 2 "$log_file"
  (cd "$SERVER" && "$PY" tools/measure_metric_builds.py "$LADDER" "$API")
  backend_down
  (cd "$SERVER" && "$PY" tools/parse_metric_phases.py "$log_file")
}

step_scaling() {
  local largest=70580
  [[ " $RUNGS " == *" $largest "* ]] || largest="${RUNGS##* }"
  (cd "$SERVER" && PHYLODELTA_STORE="$CAMPAIGN_ROOT/stores/bench" \
    "$PY" tools/measure_thread_scaling.py "$(pair_of "$largest")")
}

# Everything below reads the rf store through one API.
with_bench() {
  backend_up "$CAMPAIGN_ROOT/stores/bench" 2 "$CAMPAIGN_ROOT/logs/worker-bench.log"
  "$@"
  backend_down
}

step_latency() { with_bench bash -c "cd '$SERVER' && '$PY' tools/measure_slice_latency.py '$API'"; }
step_repeats() { with_bench bash -c "cd '$BENCH' && node harness/repeat_phylodelta.mjs"; }
step_ceiling() { with_bench bash -c "cd '$BENCH' && node harness/ceiling.mjs"; }
step_paint() { (cd "$BENCH" && node harness/phyloio_paint.mjs); }
step_endurance() { (cd "$BENCH" && node harness/endurance.mjs); }
step_navigation() { with_bench bash -c "cd '$BENCH' && node harness/navigation.mjs"; }

step_accuracy() {
  # Every rung where this campaign's comparison finished, and no others.
  local done_at
  done_at="$("$PY" -c '
import json, sys
rows = json.load(open(sys.argv[1]))["rows"]
print(*[r["leaves"] for r in rows if (r["phyloio"].get("phases") or {}).get("compareComplete")])' \
    "$RESULTS/ceiling.json")"
  for leaves in $done_at; do
    (cd "$BENCH" && node harness/accuracy.mjs "$leaves")
    (cd "$SERVER" && PHYLODELTA_STORE="$CAMPAIGN_ROOT/stores/bench" "$PY" tools/bcn_accuracy.py \
      "$RESULTS/phyloio_scores_$leaves.json" "$(pair_of "$leaves")" "$CAMPAIGN_ROOT/stores/bench")
  done
}

step_clade_repeats() {
  # Is the clades-compared figure stable? 2,493 and 2,498 stood for one rung in
  # two campaigns on byte-identical trees, so the same pair is extracted again.
  for _ in 1 2 3; do
    (cd "$BENCH" && node harness/accuracy.mjs 2500)
  done | tee "$CAMPAIGN_ROOT/logs/clades-2500.txt"
}

step_bcn_probe() {
  (cd "$BENCH" && PHYLOIO_DIST="$PHYLOIO_HOME/dist" PHYLOIO_LABEL=2.2.5 PROBE_LOADS=8 \
    PROBE_OUT="$RESULTS/phyloio_bcn_2.2.5.json" node harness/probe_version.mjs 1000)
}

step_ceiling_probe() {
  [[ " $RUNGS " == *" 17645 "* ]] || return 0
  (cd "$BENCH" && PHYLOIO_DIST="$PHYLOIO_HOME/dist" PHYLOIO_LABEL=2.2.5 COMPARE_MS=600000 \
    PROBE_OUT="$RESULTS/phyloio_ceiling_2.2.5.json" BCN_ATTEMPTS=0 \
    node harness/probe_version.mjs 17645)
}

step_transfer() { with_bench bash -c "cd '$BENCH' && node harness/transfer.mjs"; }
step_transfer_gzip() { with_bench bash -c "cd '$BENCH' && BENCH_GZIP=1 node harness/transfer.mjs"; }
step_viewport() { with_bench bash -c "cd '$BENCH' && node harness/viewport.mjs"; }

with_app() {
  backend_up "$CAMPAIGN_ROOT/stores/app" 2 "$CAMPAIGN_ROOT/logs/worker-app.log"
  "$@"
  backend_down
}
step_latency_mast() {
  with_app bash -c "cd '$SERVER' && BENCH_BUILD_FILE=server_build_app.json \
    '$PY' tools/measure_slice_latency.py '$API' mast"
}
step_transfer_app() {
  with_app bash -c "cd '$BENCH' && BENCH_BUILD_FILE=server_build_app.json BENCH_LABEL=app \
    node harness/transfer.mjs"
}
step_transfer_app_gzip() {
  with_app bash -c "cd '$BENCH' && BENCH_BUILD_FILE=server_build_app.json BENCH_LABEL=app \
    BENCH_GZIP=1 node harness/transfer.mjs"
}

step_rf_external() {
  local venv="$CAMPAIGN_ROOT/rfcheck"
  uv venv -q --clear "$venv" --python 3.12
  uv pip install -q --python "$venv/bin/python" dendropy==5.1.0 ete3==3.1.3 numpy setuptools six
  (cd "$BENCH" && "$venv/bin/python" harness/rf_external.py >"$RESULTS/rf_external.json")
}

# --- checks v0.1.0 ran by hand after the campaign, now steps of it (§34.22) ---
#
# A rehearsal (CAMPAIGN_DRY_RUN=1) runs each on its largest rung with a short
# budget, so the chain is exercised without its two hours.

step_endurance_extra() {
  # The comparison given its 30 minutes at the sizes `endurance` leaves out:
  # where phylo.io paints (17,645 to 70,580) and the largest. Since #24 the
  # runner passes its budget to load(), so this is also v0.1.0's separate
  # "long compare" check, which is not repeated.
  local rungs="17645 35290 70580 564640" budget=1800
  if [ "${CAMPAIGN_DRY_RUN:-}" = 1 ]; then rungs="${RUNGS##* }"; budget=60; fi
  (cd "$BENCH" && BENCH_RUNGS="$rungs" BENCH_BUDGET_S="$budget" BENCH_OUT=endurance_extra.json \
    node harness/endurance.mjs)
}

step_paint_extra() {
  # The paint runner at 70,580, which its default (17,645 and 35,290) leaves out.
  local rungs="70580"
  if [ "${CAMPAIGN_DRY_RUN:-}" = 1 ]; then rungs="${RUNGS##* }"; fi
  (cd "$BENCH" && BENCH_RUNGS="$rungs" BENCH_OUT=phyloio_paint_extra.json node harness/phyloio_paint.mjs)
}

step_accuracy_repeats() {
  # Table 5 at 2,500 leaves four more times: phylo.io's comparison is not
  # deterministic, so how far one draw is from the next is part of the result.
  [[ " $RUNGS " == *" 2500 "* ]] || return 0
  local scratch="$CAMPAIGN_ROOT/accuracy-repeats" pair
  rm -rf "$scratch" && mkdir -p "$scratch"
  pair="$(pair_of 2500)"
  for i in 1 2 3 4; do
    (cd "$BENCH" && BENCH_SCORES_OUT="$scratch/scores_$i.json" node harness/accuracy.mjs 2500)
    (cd "$SERVER" && BENCH_OUT="$scratch/accuracy_$i.json" PHYLODELTA_STORE="$CAMPAIGN_ROOT/stores/bench" \
      "$PY" tools/bcn_accuracy.py \
      "$scratch/scores_$i.json" "$pair" "$CAMPAIGN_ROOT/stores/bench")
  done
  (cd "$SERVER" && "$PY" tools/collect_accuracy_repeats.py "$RESULTS" "$scratch" 2500)
}

step_finish() { (cd "$BENCH" && "$PY" harness/campaign_env.py finish); }

# ---------------------------------------------------------------------- the run

ALL=(
  setup env ladder
  threads_1 threads_2 threads_10 threads_2_app
  store_rf store_app memory_2 memory_10 metric_builds scaling
  latency repeats ceiling paint endurance accuracy clade_repeats navigation
  bcn_probe ceiling_probe transfer transfer_gzip viewport
  latency_mast transfer_app transfer_app_gzip rf_external
  endurance_extra paint_extra accuracy_repeats finish
)
STEPS=("$@")
[ ${#STEPS[@]} -gt 0 ] || STEPS=("${ALL[@]}")

mkdir -p "$CAMPAIGN_ROOT/logs" "$CAMPAIGN_ROOT/stores" "$CAMPAIGN_ROOT/done"
for name in "${STEPS[@]}"; do
  stamp="$CAMPAIGN_ROOT/done/$name"
  if [ -e "$stamp" ]; then
    log "skip $name (done)"
    continue
  fi
  log "start $name"
  started=$SECONDS
  "step_$name" 2>&1 | tee -a "$CAMPAIGN_ROOT/logs/$name.log"
  date '+%FT%T' >"$stamp"
  log "done  $name in $((SECONDS - started)) s"
done
log "campaign finished"
