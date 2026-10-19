/**
 * Dropping a comparison in.
 *
 * A comparison is uploaded as one bundle — both trees and their typing data in
 * a single request — because that is what the backend accepts and what the
 * unit actually is: half a comparison is not a thing anyone can look at.
 *
 * Typing data is optional and may be **one file or two**. One file when both
 * trees are the same organism and share a table; two when they are not. That
 * choice is the user's, so it is a visible switch rather than something
 * inferred from how many files they happened to drop.
 *
 * Each table names the column whose values are the tree's leaf labels (§47),
 * chosen from its header, which is read here; the join itself is the
 * server's. `ST` is pre-selected when the header has it.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ComparisonStatus, MetricSummary } from "../api/types";
import { MetricReferenceLine } from "./MetricReferences";
import { clearDraft, loadFields, loadFiles, saveFields, saveFile, type Slot } from "./draft";
import { describeJoins } from "./isolateReport";
import { initialKey, readTableHeader, type TableHeader } from "./tableHeader";

const TREE_HINT = "Newick — .nwk, .newick, .tree";
const TABLE_HINT = "Isolate data, tab- or comma-separated — .tsv, .csv";
const TABLE_ACCEPT = ".tsv,.tab,.csv,.txt";

/** The moved-leaves metric, offered as a checkbox beside the chosen distance (§46). */
const MOVED_METRIC = "mast";

export function UploadPanel({ onReady }: { onReady: (comparisonId: string) => void }) {
  // Read once, synchronously, so the form renders filled after a refresh
  // rather than empty and then filling (draft.ts).
  const [draft] = useState(loadFields);
  const [files, setFiles] = useState<Partial<Record<Slot, File>>>({});
  const [sharedTyping, setSharedTyping] = useState(draft.sharedTyping);
  const [name, setName] = useState(draft.name);
  const [leftSpecies, setLeftSpecies] = useState(draft.leftSpecies);
  const [rightSpecies, setRightSpecies] = useState(draft.rightSpecies);
  const [leftKey, setLeftKey] = useState(draft.leftKey);
  const [rightKey, setRightKey] = useState(draft.rightKey);

  // Files are asynchronous to read back. A slot the user has filled in the
  // meantime keeps what they chose; the stored one only fills empty slots.
  useEffect(() => {
    let live = true;
    loadFiles().then((stored) => {
      if (live) setFiles((current) => ({ ...stored, ...current }));
    });
    return () => {
      live = false;
    };
  }, []);

  /*
   * What this server can compute with, asked rather than assumed.
   *
   * Metrics are plugins (§11), so a list in the client would be a second
   * registry going stale the moment one is added, and `available` is a fact
   * about the deployment — a metric whose runtime is missing is registered and
   * cannot run. If the call fails the panel simply offers nothing and the
   * upload proceeds on the server's default, which is the honest fallback:
   * not being able to choose is better than choosing something absent.
   */
  const [metrics, setMetrics] = useState<MetricSummary[]>([]);
  /*
   * Moved leaves are asked for beside the chosen metric, not instead of it
   * (§46): they are a list of leaves rather than a distance, so a comparison
   * computed with them alone would open with no score in its header. Ticked by
   * default — seconds on a demo-sized pair, and declined by name above its
   * limit without failing the comparison.
   */
  const [alsoMoved, setAlsoMoved] = useState(true);
  const movedMetric = metrics.find((metric) => metric.name === MOVED_METRIC);
  const distances = metrics.filter((metric) => metric.name !== MOVED_METRIC);
  // One metric per comparison, chosen like the bar length is: a comparison
  // is read under one metric, and the view shows the one it was computed with.
  const [chosen, setChosen] = useState<string>("");
  useEffect(() => {
    api
      .metrics()
      .then((found) => {
        // All of them, not only the usable ones: a metric the server knows
        // but cannot run is shown disabled, with the reason. Listing only the
        // usable ones hid the picker entirely when one was left, and on the
        // deployment that read as the choice having disappeared.
        setMetrics(found);
        const usable = found.filter((metric) => metric.available && metric.name !== MOVED_METRIC);
        // The remembered choice only if this server still offers it: a
        // metric whose runtime has gone would be sent and refused by name.
        const remembered = usable.some((metric) => metric.name === draft.metric)
          ? draft.metric
          : "";
        setChosen((current) => current || remembered || (usable[0]?.name ?? ""));
      })
      .catch(() => setMetrics([]));
  }, []);
  const [status, setStatus] = useState<ComparisonStatus | null>(null);
  // Entries, not the record itself, so the count and the single-item wording
  // below read from one thing.
  const failedMetrics = Object.entries(status?.metrics_failed ?? {});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    saveFields({ name, leftSpecies, rightSpecies, sharedTyping, metric: chosen, leftKey, rightKey });
  }, [name, leftSpecies, rightSpecies, sharedTyping, chosen, leftKey, rightKey]);

  const put = useCallback((slot: Slot, file: File | undefined) => {
    setFiles((current) => ({ ...current, [slot]: file }));
    void saveFile(slot, file);
  }, []);

  const leftHeader = useTableHeader(files.left_isolates);
  const rightHeader = useTableHeader(sharedTyping ? undefined : files.right_isolates);
  // When a header arrives, keep the remembered column if it has it, else ST,
  // else nothing — and then a choice is required. Keyed on the header object,
  // which changes only when a file is read, so this cannot feed itself.
  useEffect(() => {
    if (leftHeader.header) setLeftKey((key) => initialKey(leftHeader.header!.columns, key));
  }, [leftHeader.header]);
  useEffect(() => {
    if (rightHeader.header) setRightKey((key) => initialKey(rightHeader.header!.columns, key));
  }, [rightHeader.header]);

  const tablesReady =
    tableReady(files.left_isolates, leftHeader, leftKey) &&
    (sharedTyping || tableReady(files.right_isolates, rightHeader, rightKey));
  const ready = Boolean(files.left_tree && files.right_tree) && tablesReady;

  async function submit() {
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    setStatus(null);

    const form = new FormData();
    form.append("left_tree", files.left_tree!);
    form.append("right_tree", files.right_tree!);
    if (files.left_isolates) {
      form.append("left_isolates", files.left_isolates);
      form.append("left_isolates_key", leftKey);
      // Said, not inferred: a left table alone is the left tree's only (§47).
      if (sharedTyping) form.append("isolates_shared", "true");
    }
    if (!sharedTyping && files.right_isolates) {
      form.append("right_isolates", files.right_isolates);
      form.append("right_isolates_key", rightKey);
    }
    if (name.trim()) form.append("name", name.trim());
    if (leftSpecies.trim()) form.append("left_species", leftSpecies.trim());
    if (rightSpecies.trim()) form.append("right_species", rightSpecies.trim());
    const wanted = [chosen, alsoMoved && movedMetric?.available ? MOVED_METRIC : ""].filter(Boolean);
    if (wanted.length) form.append("metrics", wanted.join(","));

    try {
      const accepted = await api.upload(form);
      // The server computes off the request path, so the only honest thing to
      // do here is poll — a comparison of two 500k-node trees is minutes.
      await poll(accepted.id, setStatus);
      // Done: the comparison is in the list now, so the draft has served.
      await clearDraft();
      onReady(accepted.id);
    } catch (failed) {
      setError(
        failed instanceof ApiError
          ? `${failed.message}${failed.hint ? ` — ${failed.hint}` : ""}`
          : String(failed),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="upload">
      <h2>New comparison</h2>
      <p className="upload-lead">
        Two trees, and optionally the isolate data that goes with them. They are
        uploaded together and compared on the server.
      </p>

      <div className="drop-row">
        <DropZone
          label="Left tree"
          hint={TREE_HINT}
          accept=".nwk,.newick,.tree,.txt"
          file={files.left_tree}
          onFile={(f) => put("left_tree", f)}
        />
        <DropZone
          label="Right tree"
          hint={TREE_HINT}
          accept=".nwk,.newick,.tree,.txt"
          file={files.right_tree}
          onFile={(f) => put("right_tree", f)}
        />
      </div>

      <fieldset className="typing">
        <legend>Isolate data (optional)</legend>
        <label className="switch">
          <input
            type="checkbox"
            checked={sharedTyping}
            onChange={(event) => setSharedTyping(event.target.checked)}
          />
          One table for both trees
          <span className="switch-note">
            Uncheck when the two trees are different organisms and each has its own.
          </span>
        </label>

        <div className="drop-row">
          <div className="table-slot">
            <DropZone
              label={sharedTyping ? "Isolate data" : "Left isolate data"}
              hint={TABLE_HINT}
              accept={TABLE_ACCEPT}
              file={files.left_isolates}
              onFile={(f) => put("left_isolates", f)}
            />
            <KeyColumn read={leftHeader} value={leftKey} onChange={setLeftKey} />
          </div>
          {sharedTyping ? null : (
            <div className="table-slot">
              <DropZone
                label="Right isolate data"
                hint={TABLE_HINT}
                accept={TABLE_ACCEPT}
                file={files.right_isolates}
                onFile={(f) => put("right_isolates", f)}
              />
              <KeyColumn read={rightHeader} value={rightKey} onChange={setRightKey} />
            </div>
          )}
        </div>
      </fieldset>

      <div className="fields">
        <label>
          Name
          <input
            type="text"
            value={name}
            placeholder="defaults to the two filenames"
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label>
          Left species
          <input
            type="text"
            value={leftSpecies}
            placeholder="optional"
            onChange={(event) => setLeftSpecies(event.target.value)}
          />
        </label>
        <label>
          Right species
          <input
            type="text"
            value={rightSpecies}
            placeholder="optional"
            onChange={(event) => setRightSpecies(event.target.value)}
          />
        </label>
        {distances.length > 0 ? (
          <label className="upload-metric">
            Compare with
            <select value={chosen} onChange={(event) => setChosen(event.target.value)}>
              {distances.map((metric) => (
                <option key={metric.name} value={metric.name} disabled={!metric.available}>
                  {metric.available ? metric.title : `${metric.title} — not installed on this server`}
                </option>
              ))}
            </select>
            {/* The metric's name and where its computation comes from (§42). Its
                description is not repeated here: it is written for whoever
                maintains the metric, says much the same as the reference line,
                and stays in the manifest and in GET /metrics. */}
            <MetricReferenceLine
              reference={metrics.find((metric) => metric.name === chosen)?.reference ?? null}
            />
          </label>
        ) : null}
        {movedMetric ? (
          <label className="switch upload-moved">
            <input
              type="checkbox"
              checked={alsoMoved && movedMetric.available}
              disabled={!movedMetric.available}
              onChange={(event) => setAlsoMoved(event.target.checked)}
            />
            Also find moved leaves (MAST)
            <span className="switch-note">
              {movedMetric.available
                ? "The leaves outside the largest subtree both trees agree on, to show on the trees."
                : "Not installed on this server."}
            </span>
            {movedMetric.available ? <MetricReferenceLine reference={movedMetric.reference ?? null} /> : null}
          </label>
        ) : null}
      </div>

      <p className="field-help">
        {/* Not decoration: sequence types are numbered per species, so across
            species identical labels match no actual organism. Declaring them
            is what lets the result say so. */}
        Naming both species lets the result say whether matching leaf labels
        mean the same organisms. Left blank, it reports that it could not check.
      </p>

      <button type="button" className="primary" disabled={!ready || busy} onClick={submit}>
        {busy ? "Uploading…" : "Upload and compare"}
      </button>

      {status ? (
        <p className={`upload-status ${status.status}`}>
          {status.status === "pending"
            ? "Queued — waiting for a worker."
            : status.status === "running"
              ? "Computing the comparison…"
              : status.status === "failed"
                ? `Failed: ${status.error ?? "no reason given"}`
                : "Ready."}
        </p>
      ) : null}
      {/*
        A metric that was asked for and could not be computed.

        Separate from `error`, which means the comparison failed: this one is
        ready and usable, and only part of what was requested is missing. Saying
        so here is the whole point — the comparison arrives with the metric
        simply absent, which on its own is indistinguishable from never having
        asked for it.
      */}
      {failedMetrics.length > 0 ? (
        <p className="upload-status partial">
          {failedMetrics.length === 1
            ? `Computed, but ${failedMetrics[0][0]} could not be: ${failedMetrics[0][1]}`
            : `Computed, but ${failedMetrics.length} metrics could not be: ` +
              failedMetrics.map(([name, why]) => `${name} (${why})`).join("; ")}
        </p>
      ) : null}
      {/* How each table met its tree (§47): what matched no leaf, and a
          table not used at all because nothing did. */}
      {status?.status === "ready"
        ? describeJoins(status.isolates).map((line) => (
            <p key={line} className={`upload-status ${line.includes("not used") ? "partial" : ""}`}>
              {line}
            </p>
          ))
        : null}
      {error ? <p className="upload-status failed">{error}</p> : null}
    </section>
  );
}

/** A table's header as read in the browser: nothing yet, read, or refused. */
interface HeaderRead {
  file: File | undefined;
  header?: TableHeader;
  error?: string;
}

/**
 * Read a table's header whenever its file changes.
 *
 * Depends on the `File` alone — an object that changes only when a file is
 * dropped or restored — so a re-render cannot start another read (the shape
 * of bug `useTypingData` has had three times).
 */
function useTableHeader(file: File | undefined): HeaderRead {
  const [read, setRead] = useState<HeaderRead>({ file: undefined });
  useEffect(() => {
    if (!file) {
      setRead({ file: undefined });
      return;
    }
    let live = true;
    setRead({ file });
    readTableHeader(file)
      .then((header) => live && setRead({ file, header }))
      .catch((failed: unknown) =>
        live && setRead({ file, error: failed instanceof Error ? failed.message : String(failed) }),
      );
    return () => {
      live = false;
    };
  }, [file]);
  // A read still in flight for the previous file is not this file's answer.
  return read.file === file ? read : { file };
}

/** No table, or a table whose header was read and whose key it has. */
export function tableReady(file: File | undefined, read: HeaderRead, key: string): boolean {
  if (!file) return true;
  return Boolean(read.header && key && read.header.columns.includes(key));
}

/**
 * The key-column choice under a table's drop zone.
 *
 * Disabled until a file has been read. With no `ST` in the header nothing is
 * pre-selected: taking the first column on the user's behalf would join on a
 * guess, and a wrong guess looks like data rather than like a mistake.
 */
export function KeyColumn({
  read,
  value,
  onChange,
}: {
  read: HeaderRead;
  value: string;
  onChange: (key: string) => void;
}) {
  const columns = read.header?.columns ?? [];
  return (
    <label className="key-column">
      Column with the leaf names
      <select
        value={columns.includes(value) ? value : ""}
        disabled={!read.header}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="" disabled>
          {read.file ? (read.header ? "Choose a column…" : read.error ? "—" : "Reading…") : "Choose a file first"}
        </option>
        {columns.map((column) => (
          <option key={column} value={column}>
            {column}
          </option>
        ))}
      </select>
      {read.error ? (
        <span className="key-column-note failed">{read.error}</span>
      ) : read.header && !columns.includes(value) ? (
        <span className="key-column-note">
          Choose the column whose values are the tree's leaf labels.
        </span>
      ) : read.header ? (
        <span className="key-column-note">
          {read.header.format.toUpperCase()}, {columns.length} columns.
        </span>
      ) : null}
    </label>
  );
}

/** Poll until the comparison leaves `pending`/`running`. */
async function poll(
  comparisonId: string,
  report: (status: ComparisonStatus) => void,
): Promise<void> {
  // Backs off so a long computation does not become a request every second for
  // several minutes.
  let wait = 500;
  for (;;) {
    const status = await api.status(comparisonId);
    report(status);
    if (status.status === "ready") return;
    if (status.status === "failed") {
      throw new ApiError(400, {
        detail: status.error ?? "The comparison failed.",
        code: "comparison_failed",
      });
    }
    await new Promise((resume) => setTimeout(resume, wait));
    wait = Math.min(wait * 1.5, 5_000);
  }
}

function DropZone({
  label,
  hint,
  accept,
  file,
  onFile,
}: {
  label: string;
  hint: string;
  accept: string;
  file: File | undefined;
  onFile: (file: File | undefined) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  return (
    <div
      className={`drop-zone${over ? " over" : ""}${file ? " filled" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        onFile(event.dataTransfer.files[0]);
      }}
      onClick={() => input.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") input.current?.click();
      }}
    >
      <p className="drop-label">{label}</p>
      {file ? (
        <>
          <p className="drop-file">{file.name}</p>
          <p className="drop-hint">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
          <button
            type="button"
            className="link-button"
            onClick={(event) => {
              event.stopPropagation();
              onFile(undefined);
            }}
          >
            Remove
          </button>
        </>
      ) : (
        <p className="drop-hint">Drop a file here, or click to choose. {hint}</p>
      )}
      <input
        ref={input}
        type="file"
        accept={accept}
        hidden
        onChange={(event) => onFile(event.target.files?.[0])}
      />
    </div>
  );
}
