/**
 * The application shell.
 *
 * Two states: choosing a comparison, and looking at one. Everything else —
 * navigation, menus, slicing — belongs to the comparison view.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api/client";
import { poll } from "./api/poll";
import { headlineBefore, rebuildLabel, sideName } from "./comparison/reroot";
import { REROOT_COST } from "./comparison/menuItems";
import { ComparisonView } from "./comparison/ComparisonView";
import { UploadPanel } from "./upload/UploadPanel";
import { CheckboxMenu } from "./ui/CheckboxMenu";
import { Notice } from "./ui/Notice";
import { useUrlState, type ViewOptions } from "./useUrlState";
import { COLOR_TARGETS } from "./comparison/colorTarget";
import type {
  ComparisonStatus,
  ComparisonSummary,
  DatasetsResponse,
  MetricSummary,
  PairSummary,
  WhoAmI,
} from "./api/types";
import {
  headline,
  isEntry,
  metricTitle,
  presentationsOf,
  shownPresentation,
  viewMetric,
} from "./comparison/metric";
import { pairName, treeName } from "./names";
import { describeKey, unusedTables } from "./upload/isolateReport";

declare global {
  interface Window {
    __phylodeltaApp?: {
      reroot: (side: 0 | 1, storedId: number, replace?: boolean) => Promise<void>;
    };
  }
}

export function App() {
  const [me, setMe] = useState<WhoAmI | null>(null);
  const [pairs, setPairs] = useState<PairSummary[]>([]);
  const [datasets, setDatasets] = useState<DatasetsResponse | null>(null);
  const [exporting, setExporting] = useState(false);
  /** The comparison a removal was asked about, until it is confirmed or not. */
  const [removing, setRemoving] = useState<PairSummary | null>(null);
  const [removeBusy, setRemoveBusy] = useState(false);
  const [view, setView] = useUrlState();

  /*
   * The View menu reads and writes the URL directly rather than keeping its
   * own copy. Two sources of truth for the same switch is how they came to
   * disagree: the menu remembered the choice, the URL did not, and a refresh
   * restored the navigation with the presentation reset under it.
   */
  const options = view.options;
  const setOptions = useCallback(
    (change: Partial<ViewOptions>) =>
      setView({
        comparison: view.comparison,
        left: view.left,
        right: view.right,
        options: { ...view.options, ...change },
      }),
    [setView, view],
  );
  const [chosen, setChosen] = useState<PairSummary | null>(null);
  const [summary, setSummary] = useState<ComparisonSummary | null>(null);
  /** The open comparison's /status: its isolate joins (§47) and its re-root relations (§56). */
  const [chosenStatus, setChosenStatus] = useState<ComparisonStatus | null>(null);
  const isolateJoins = chosenStatus?.isolates;
  /**
   * A re-root being built (§56). Held here, not in the view: the user stays on
   * the original and keeps using it, and the build outlives anything they open
   * meanwhile.
   */
  const [rebuild, setRebuild] = useState<{
    from: string;
    metric: string;
    what: string;
    id?: string;
    status?: ComparisonStatus["status"];
    error?: string;
    /** Ready, but the user had moved on: offered rather than opened. */
    waiting?: PairSummary;
  } | null>(null);
  /** The re-root a menu item asked for, until it is confirmed or not. */
  const [asking, setAsking] = useState<{ side: 0 | 1; storedId: number } | null>(null);
  const [replaceOriginal, setReplaceOriginal] = useState(false);
  /** An old link to a comparison its owner replaced by re-rooting: where it went. */
  const [movedTo, setMovedTo] = useState<{ from: string; to: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  /**
   * What the server can compute, and so how each metric's comparison can be
   * coloured and numbered (§52). Undefined until asked; a failure leaves it so,
   * and every comparison is then offered the shared divergence gradient.
   */
  const [metrics, setMetrics] = useState<MetricSummary[] | undefined>(undefined);
  useEffect(() => {
    api.metrics().then(setMetrics).catch(() => setMetrics(undefined));
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [who, datasets] = await Promise.all([api.me(), api.datasets()]);
      setMe(who);
      setDatasets(datasets);
      setPairs(datasets.pairs);
      setError(null);
    } catch (failed) {
      setError(failed instanceof ApiError ? failed.message : String(failed));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const remove = useCallback(
    async (pair: PairSummary) => {
      setRemoveBusy(true);
      try {
        // This metric's comparison only: the pair's others stay (§52).
        await api.removeComparison(pair.id, pair.metric || undefined);
        // Leave the comparison if it is the one being looked at; its slices
        // would 404 from the next navigation onwards.
        if (chosen && isEntry(chosen, pair.id, viewMetric(pair))) {
          setChosen(null);
          setView({ comparison: null, left: [], right: [] });
        }
        setRemoving(null);
        await refresh();
      } catch (failed) {
        setError(failed instanceof ApiError ? failed.message : String(failed));
        setRemoving(null);
      } finally {
        setRemoveBusy(false);
      }
    },
    [chosen, refresh, setView],
  );

  // Restore from the URL once the listing arrives. A refresh on a comparison
  // must come back to that comparison, not to the chooser: getting back to a
  // view of two large trees is not free, and a URL that does not name what it
  // shows cannot be shared.
  useEffect(() => {
    if (!view.comparison) return;
    if (chosen && isEntry(chosen, view.comparison, options.metric)) return;
    const found = pairs.find((pair) => isEntry(pair, view.comparison as string, options.metric));
    if (found) setChosen(found);
  }, [pairs, view.comparison, options.metric, chosen]);

  useEffect(() => {
    if (!chosen || chosen.status !== "ready") {
      setSummary(null);
      return;
    }
    api
      .comparison(chosen.id, viewMetric(chosen))
      .then(setSummary)
      .catch(() => setSummary(null));
  }, [chosen]);

  // /status says how each uploaded isolate table met its tree (§47). Asked on
  // every opening: an upload switches straight to the comparison, and this is
  // where a table joined on the wrong column can say so.
  useEffect(() => {
    setChosenStatus(null);
    if (!chosen || chosen.status !== "ready") return;
    let live = true;
    api
      .status(chosen.id)
      .then((status) => {
        if (live) setChosenStatus(status);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [chosen]);

  // One comparison, one metric (§52): its number in the header, and only the
  // colourings it declares in the menu.
  const metric = chosen ? viewMetric(chosen) : null;
  const manifest = metric ? metrics?.find((m) => m.name === metric) : undefined;
  const top = summary ? headline(summary, manifest) : null;
  const offered = metric ? presentationsOf(metric, metrics) : [];
  const shown = shownPresentation(options.colour, offered);
  const before = headlineBefore(summary, manifest, chosenStatus?.reroot, metric);

  // --- re-rooting (§56) -------------------------------------------------------
  // Refs, because a build takes minutes and must act on what the user is
  // looking at when it ends, not on what they were looking at when it began.
  const chosenRef = useRef<string | null>(null);
  chosenRef.current = chosen?.id ?? null;
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const treeNames = chosen
    ? { left: treeName(chosen.left, datasets), right: treeName(chosen.right, datasets) }
    : undefined;

  const startReroot = useCallback(
    async (ask: { side: 0 | 1; storedId: number }, replace: boolean) => {
      if (!chosen) return;
      const from = chosen.id;
      const wanted = viewMetric(chosen);
      const what = sideName(ask.side, treeNames);
      setAsking(null);
      setRebuild({ from, metric: wanted, what, status: "pending" });
      try {
        const accepted = await api.reroot(from, {
          side: ask.side === 0 ? "left" : "right",
          node: ask.storedId,
          replace,
        });
        setRebuild((current) => current && { ...current, id: accepted.id });
        await poll(accepted.id, (status) =>
          setRebuild((current) => current && { ...current, status: status.status }),
        );
        const listing = await api.datasets();
        setDatasets(listing);
        setPairs(listing.pairs);
        const built =
          listing.pairs.find((pair) => isEntry(pair, accepted.id, wanted)) ??
          listing.pairs.find((pair) => pair.id === accepted.id);
        if (built && chosenRef.current === from) {
          // Opened at its root with the current budget: new ids, so nothing
          // the slice cache holds can be served for it.
          setRebuild(null);
          setChosen(built);
          setView({
            comparison: built.id,
            left: [],
            right: [],
            options: { ...optionsRef.current, metric: viewMetric(built) },
          });
        } else {
          setRebuild((current) => current && { ...current, status: "ready", waiting: built });
        }
      } catch (failed) {
        // The original is untouched: a failed re-root is only a failed new comparison.
        setRebuild(
          (current) =>
            current && {
              ...current,
              status: "failed",
              error: failed instanceof ApiError ? failed.message : String(failed),
            },
        );
        void refresh();
      }
    },
    [chosen, treeNames?.left, treeNames?.right, setView, refresh],
  );
  const building = rebuild !== null && !rebuild.error && !rebuild.waiting;
  // The same path the dialog's confirm takes, for the re-root benchmark
  // (`bench/harness/reroot.mjs`) to start from: no menu, no dialog, the
  // build, the polling and the opening all as a user gets them.
  const startRerootNow = useRef(startReroot);
  startRerootNow.current = startReroot;
  useEffect(() => {
    window.__phylodeltaApp = {
      reroot: (side, storedId, replace = false) => startRerootNow.current({ side, storedId }, replace),
    };
    return () => {
      delete window.__phylodeltaApp;
    };
  }, []);
  const open = useCallback(
    (pair: PairSummary) => {
      setChosen(pair);
      setView({
        comparison: pair.id,
        left: [],
        right: [],
        options: { ...optionsRef.current, metric: viewMetric(pair) },
      });
    },
    [setView],
  );
  const previous = chosenStatus?.rerooted_from
    ? pairs.find((pair) => isEntry(pair, chosenStatus.rerooted_from as string, metric))
    : undefined;
  const successor = chosenStatus?.superseded_by
    ? pairs.find((pair) => isEntry(pair, chosenStatus.superseded_by as string, metric))
    : undefined;

  // An old link to a comparison its owner replaced by re-rooting answers 410
  // with where it went (§56): said, with a link, rather than an empty page.
  useEffect(() => {
    setMovedTo(null);
    if (!view.comparison || !datasets) return;
    if (pairs.some((pair) => pair.id === view.comparison)) return;
    let live = true;
    const asked = view.comparison;
    api.status(asked).catch((failed) => {
      if (live && failed instanceof ApiError && failed.code === "comparison_rerooted" && failed.movedTo) {
        setMovedTo({ from: asked, to: failed.movedTo });
      }
    });
    return () => {
      live = false;
    };
  }, [view.comparison, pairs, datasets]);
  const movedPair = movedTo ? pairs.find((pair) => pair.id === movedTo.to) : undefined;

  return (
    <div className="app">
      <header className="app-bar">
        <h1>PhyloDelta</h1>
        <p className="tagline">Compare large phylogenetic trees</p>
        <span className="spacer" />
        {top ? (
          <span className="headline" title={top.title}>
            {top.label} <strong>{top.value.toLocaleString()}</strong>
            {top.to !== undefined ? (
              <>
                {" to "}
                <strong>{top.to.toLocaleString()}</strong>
              </>
            ) : null}
            {top.normalised !== undefined ? (
              <em> ({top.normalised.toFixed(3)} normalised)</em>
            ) : null}
            {top.of !== undefined ? <em> of {top.of.toLocaleString()}</em> : null}
            {before ? (
              <em className="headline-before" title="The same metric for the comparison this one re-roots (§56)">
                {" "}
                (before re-rooting: {before.value.toLocaleString()}
                {before.to !== undefined ? ` to ${before.to.toLocaleString()}` : ""})
              </em>
            ) : null}
          </span>
        ) : null}
        {rebuild ? (
          <span
            className={`chip rebuild ${rebuild.error ? "warn" : ""}`}
            role="status"
            title={rebuild.error ?? `${REROOT_COST}; this comparison stays usable meanwhile`}
          >
            Re-rooting {rebuild.what}: {rebuild.error ? `failed — ${rebuild.error}` : rebuildLabel(rebuild.status)}
            {rebuild.waiting ? (
              <button
                type="button"
                className="chip-action"
                onClick={() => {
                  const ready = rebuild.waiting as PairSummary;
                  setRebuild(null);
                  open(ready);
                }}
              >
                Open
              </button>
            ) : null}
            {rebuild.error || rebuild.waiting ? (
              <button
                type="button"
                className="chip-action"
                aria-label="Dismiss"
                onClick={() => setRebuild(null)}
              >
                ×
              </button>
            ) : null}
          </span>
        ) : null}
        {chosen && previous ? (
          <button
            type="button"
            className="back-button"
            title={`Open ${pairName(previous, datasets)}, the comparison this one re-roots`}
            onClick={() => open(previous)}
          >
            Back to the previous rooting
          </button>
        ) : null}
        {me?.mock ? (
          <span className="chip warn" title="No credentials are being checked">
            demo mode
          </span>
        ) : me ? (
          <span className="chip">{me.display_name || me.owner_id}</span>
        ) : null}
        {chosen ? (
          /*
           * One menu rather than a checkbox each. Three switches across a
           * header is a row of unlabelled state; a menu names what it holds
           * and leaves room for the next one.
           */
          <CheckboxMenu
            summary="View options"
            align="right"
            items={[
              // What colours the trees: only what this comparison's metric
              // offers (§52), one at a time, each with its own legend — so a
              // radio group rather than switches.
              ...offered.map((option, index) => ({
                key: `colour-by:${option.name}`,
                label: option.label,
                checked: shown?.name === option.name,
                note: option.description,
                group: "colour-by",
                heading: index === 0 ? "Colour the trees by" : undefined,
              })),
              {
                key: "colour-by:none",
                label: "Nothing",
                checked: shown === null,
                note: "The trees in black",
                group: "colour-by",
              },
              {
                key: "typing",
                label: "Isolate data",
                checked: options.typing,
                heading: "Show",
                note: describeKey(isolateJoins) ?? "A bar of isolates on each leaf",
              },
              {
                key: "clades",
                label: "Clade sizes",
                checked: options.cladeSizes,
                note: "Label every collapsed clade with its leaf count",
              },
              {
                key: "lengths",
                label: "Branch lengths",
                checked: options.lengths,
                note: "Each branch's length where it fits; zoom in for more",
              },
              // How the trees are drawn: one of two, so a radio pair, like
              // where the divergence goes.
              {
                key: "layout:cladogram",
                label: "Cladogram",
                checked: options.layout === "cladogram",
                note: "Branch points by depth: read the topology",
                group: "layout",
                heading: "Draw the trees as",
              },
              {
                key: "layout:phylogram",
                label: "Phylogram",
                checked: options.layout === "phylogram",
                note: "Branch lengths to scale: read the distance",
                group: "layout",
              },
              // Only a phylogram draws lengths, so the scale is offered only
              // there; a cladogram ignores it either way.
              ...(options.layout === "phylogram"
                ? [
                    {
                      key: "scale:linear",
                      label: "Linear",
                      checked: options.lengthScale === "linear",
                      note: "Lengths exactly to scale",
                      group: "length-scale",
                      heading: "Branch length scale",
                    },
                    {
                      key: "scale:log",
                      label: "Logarithmic",
                      checked: options.lengthScale === "log",
                      note: "log(1 + length): long branches no longer flatten the rest",
                      group: "length-scale",
                    },
                  ]
                : []),
              // Which clades the budget opens (§6.1, §55.1): a request to the
              // server, so switching fetches new slices.
              {
                key: "order:size",
                label: "Largest clades first",
                checked: options.order !== "difference",
                note: "Detail goes to the biggest clades",
                group: "order",
                heading: "Open clades",
              },
              {
                key: "order:difference",
                label: "Most different first",
                checked: options.order === "difference",
                note: "Detail goes where the two trees disagree most",
                group: "order",
              },
              // How a wedge's height reads (§55.2). Drawing only.
              {
                key: "wedges:proportional",
                label: "Proportional",
                checked: options.wedges !== "log",
                note: "Height in proportion to the leaves hidden; the largest wedge on screen is full height",
                group: "wedges",
                heading: "Wedge size",
              },
              {
                key: "wedges:log",
                label: "Logarithmic",
                checked: options.wedges === "log",
                note: "Height by log2 of the leaves hidden: small clades stay visible",
                group: "wedges",
              },
              {
                key: "match-order",
                label: "Order to match the other tree",
                checked: options.matchOrder,
                heading: "Siblings",
                note: "Each node's children in the order of their counterparts in the other tree. Only the drawing changes",
              },
              // Where the gradient lands, not whether it is on — so the choice
              // is offered only while there is one to place.
              ...(shown?.kind === "gradient"
                ? COLOR_TARGETS.map((target, index) => ({
                    key: `colour:${target.key}`,
                    label: target.label,
                    checked: options.colorTarget === target.key,
                    note: target.note,
                    group: "colour-target",
                    heading: index === 0 ? "Colour the divergence on" : undefined,
                  }))
                : []),
            ]}
            onToggle={(key) => {
              if (key.startsWith("colour-by:")) setOptions({ colour: key.slice("colour-by:".length) });
              if (key === "typing") setOptions({ typing: !options.typing });
              if (key === "clades") setOptions({ cladeSizes: !options.cladeSizes });
              if (key === "lengths") setOptions({ lengths: !options.lengths });
              if (key.startsWith("scale:")) {
                setOptions({ lengthScale: key.slice("scale:".length) as ViewOptions["lengthScale"] });
              }
              if (key.startsWith("layout:")) {
                setOptions({ layout: key.slice("layout:".length) as ViewOptions["layout"] });
              }
              if (key.startsWith("order:")) {
                setOptions({ order: key.slice("order:".length) as ViewOptions["order"] });
              }
              if (key.startsWith("wedges:")) {
                setOptions({ wedges: key.slice("wedges:".length) as ViewOptions["wedges"] });
              }
              if (key === "match-order") setOptions({ matchOrder: !options.matchOrder });
              if (key.startsWith("colour:")) {
                setOptions({
                  colorTarget: key.slice("colour:".length) as ViewOptions["colorTarget"],
                });
              }
            }}
          />
        ) : null}
        {chosen ? (
          <button
            type="button"
            className="back-button"
            onClick={() => setExporting(true)}
            title="A report with the trees as shown and the comparison values"
          >
            Export
          </button>
        ) : null}
        {chosen ? (
          <button
            type="button"
            className="back-button"
            onClick={() => {
              setChosen(null);
              setView({ comparison: null, left: [], right: [] });
            }}
          >
            <span aria-hidden="true">←</span> Back
          </button>
        ) : null}
      </header>

      {error ? <p className="app-error">{error}</p> : null}

      {removing ? (
        <Notice
          title={`Remove ${pairName(removing, datasets)} (${metricTitle(viewMetric(removing), metrics)})?`}
          detail={
            // Said as it will happen: a pair listed under other metrics keeps
            // its trees, and only this metric's comparison goes (§52).
            pairs.filter((pair) => pair.id === removing.id).length > 1
              ? "This deletes this metric's comparison. The same trees compared by " +
                "another metric are kept. It cannot be undone."
              : "This deletes the comparison, both trees, and any isolate data only it " +
                "was using. Trees another comparison still needs are kept. It cannot be undone."
          }
          confirm={{ label: "Remove", onConfirm: () => void remove(removing) }}
          busy={removeBusy}
          onDismiss={() => setRemoving(null)}
        />
      ) : null}

      {asking && chosen ? (
        <Notice
          title={`Re-root ${sideName(asking.side, treeNames)} above this node?`}
          detail={
            `${REROOT_COST}, as an upload is: seconds for a few thousand leaves, ` +
            "minutes near 500,000. This comparison stays open and usable meanwhile; " +
            "the re-rooted one opens when it is ready."
          }
          confirm={{
            label: replaceOriginal ? "Re-root and replace" : "Re-root",
            onConfirm: () => void startReroot(asking, replaceOriginal),
          }}
          onDismiss={() => setAsking(null)}
        >
          <label className="notice-option">
            <input
              type="checkbox"
              checked={replaceOriginal}
              onChange={(event) => setReplaceOriginal(event.target.checked)}
            />{" "}
            Replace this comparison: delete it once the re-rooted one is ready. It cannot be undone.
          </label>
        </Notice>
      ) : null}

      {chosen ? (
        <>
          {chosen.caution ? <p className="caution">{chosen.caution}</p> : null}
          {successor ? (
            <p className="caution">
              This comparison was re-rooted as {pairName(successor, datasets)}.{" "}
              <button type="button" className="link-button" onClick={() => open(successor)}>
                Open it
              </button>
            </p>
          ) : null}
          {/* A table that matched no leaf was not used (§47). Said above the
              trees, not only in a menu: otherwise its side simply has no bars,
              which looks like a tree without isolate data, not a mistake. */}
          {unusedTables(isolateJoins).map((line) => (
            <p key={line} className="caution">
              {line}
            </p>
          ))}
          <ComparisonView
            key={`${chosen.id}|${metric}`}
            pair={chosen}
            initial={
              view.comparison === chosen.id
                ? { left: view.left, right: view.right }
                : undefined
            }
            onNavigate={(l, r) => setView({ comparison: chosen.id, left: l, right: r })}
            isolateSets={isolateSetsFor(chosen, datasets)}
            names={{
              pair: pairName(chosen, datasets),
              left: treeName(chosen.left, datasets),
              right: treeName(chosen.right, datasets),
            }}
            options={options}
            onOptions={setOptions}
            summary={summary}
            metric={metric ?? "rf"}
            shown={shown}
            exporting={exporting}
            onExportClose={() => setExporting(false)}
            reroot={{
              busy: building ? "A re-root is already being built" : undefined,
              onReroot: (side, storedId) => {
                setReplaceOriginal(false);
                setAsking({ side, storedId });
              },
            }}
          />
        </>
      ) : (
        <div className="chooser">
          {movedTo ? (
            <p className="caution moved">
              That comparison was re-rooted and replaced
              {movedPair ? ` by ${pairName(movedPair, datasets)}` : ""}.{" "}
              {movedPair ? (
                <button type="button" className="link-button" onClick={() => open(movedPair)}>
                  Open it
                </button>
              ) : null}
            </p>
          ) : null}
          <section className="existing">
            <h2>Your comparisons</h2>
            {pairs.length === 0 ? (
              <p className="empty">Nothing yet. Upload two trees to begin.</p>
            ) : (
              <ul className="pair-list">
                {pairs.map((pair) => (
                  <li key={`${pair.id}|${viewMetric(pair)}`}>
                    {/*
                      The remove control is a SIBLING of the row, not inside
                      it: a button within a button is invalid markup, and the
                      browser's own repair of it puts the destructive action
                      where a click meant to open the comparison can land.
                    */}
                    <button
                      type="button"
                      className="pair"
                      disabled={pair.status !== "ready"}
                      onClick={() => {
                        setChosen(pair);
                        setView({
                          comparison: pair.id,
                          left: [],
                          right: [],
                          // A new comparison opens with its metric's first colouring.
                          options: { ...options, metric: viewMetric(pair), colour: "" },
                        });
                      }}
                    >
                      <span className="pair-name">{pairName(pair, datasets)}</span>
                      {/* One comparison, one metric (§52): which one, named here. */}
                      <span className="pair-metric">{metricTitle(viewMetric(pair), metrics)}</span>
                      <span className={`pair-status ${pair.status}`}>{pair.status}</span>
                      {pair.status === "ready" ? (
                        <span className="pair-detail">
                          {pair.shared_leaves.toLocaleString()} shared leaves
                        </span>
                      ) : null}
                      {pair.error ? <span className="pair-detail">{pair.error}</span> : null}
                      {pair.superseded_by ? (
                        <span className="pair-detail superseded">
                          superseded by{" "}
                          {(() => {
                            const next = pairs.find((other) => other.id === pair.superseded_by);
                            return next ? pairName(next, datasets) : "a re-rooted comparison";
                          })()}
                        </span>
                      ) : null}
                      {pair.rerooted_from ? <span className="pair-detail">re-rooted</span> : null}
                    </button>
                    <button
                      type="button"
                      className="pair-remove"
                      title={`Remove ${pairName(pair, datasets)} (${metricTitle(viewMetric(pair), metrics)})`}
                      aria-label={`Remove ${pairName(pair, datasets)} (${metricTitle(viewMetric(pair), metrics)})`}
                      onClick={() => setRemoving(pair)}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <UploadPanel
            metrics={metrics}
            onReady={async (comparisonId) => {
              await refresh();
              const datasets = await api.datasets();
              setPairs(datasets.pairs);
              const built = datasets.pairs.find((pair) => pair.id === comparisonId);
              if (built) {
                setChosen(built);
                setView({
                  comparison: built.id,
                  left: [],
                  right: [],
                  options: { ...options, metric: viewMetric(built), colour: "" },
                });
              }
            }}
          />
        </div>
      )}
    </div>
  );
}


/**
 * Which isolate store holds each side's typing data.
 *
 * A tree's store is keyed by its species for catalogue data and by its dataset
 * id for an upload (§24.5), so the answer comes from the listing rather than
 * being assembled here. Null where a tree has none, which is the common case
 * before anyone uploads a table.
 *
 * The species is tried only for a catalogue tree, which is the one with a
 * method: the catalogue reads it from the filename and an upload has none
 * (§24.6). An uploaded tree's table is stored under its own id, so falling
 * back to its *declared* species joined an upload declared "vibrio" to the
 * demo vibrio table — data nobody uploaded with it, drawn as though they had
 * (§47).
 */
function isolateSetsFor(
  pair: PairSummary,
  datasets: DatasetsResponse | null,
): [string | null, string | null] {
  if (!datasets) return [null, null];
  const have = new Set(datasets.isolates.map((isolate) => isolate.species));
  const forTree = (treeId: string): string | null => {
    const tree = datasets.trees.find((candidate) => candidate.id === treeId);
    const catalogue = Boolean(tree?.method);
    for (const candidate of [treeId, catalogue ? tree?.species : undefined]) {
      if (candidate && have.has(candidate)) return candidate;
    }
    return null;
  };
  return [forTree(pair.left), forTree(pair.right)];
}
