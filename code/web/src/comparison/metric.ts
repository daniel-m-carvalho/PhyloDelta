/**
 * One comparison is one metric (§52).
 *
 * A pair of trees computed with several metrics is listed as one comparison per
 * metric, and a comparison is read, numbered and coloured only as its metric
 * declares: the header shows that metric's number, and the View menu offers
 * that metric's presentations and no others. Nothing here names a metric. What
 * each one offers comes from GET /metrics, so a metric added on the server —
 * SPR, triplet's own colouring — reaches the view with no change to this file.
 */

import type { ComparisonSummary, MetricSummary, PairSummary, Presentation } from "../api/types";

/**
 * The metric a listing entry is the comparison by.
 *
 * The entry's own `metric` where the server says it. A server from before
 * §52 lists a pair once with all its metrics; RF is then preferred where
 * computed, as the view always did, since the catalogue pairs carry it.
 */
export function viewMetric(pair: Pick<PairSummary, "metrics" | "metric">): string {
  if (pair.metric) return pair.metric;
  if (pair.metrics.includes("rf")) return "rf";
  return pair.metrics[0] ?? "rf";
}

/** Whether a listing entry is the comparison a link names: same pair, same metric. */
export function isEntry(
  pair: Pick<PairSummary, "id" | "metrics" | "metric">,
  id: string,
  metric: string | null,
): boolean {
  return pair.id === id && (metric === null || viewMetric(pair) === metric);
}

/**
 * The colouring every metric has when its manifest says nothing: the shared
 * correspondence's gradient. Also what is offered while /metrics is loading,
 * so the view opens coloured rather than waiting.
 */
const DIVERGENCE: Presentation = {
  name: "divergence",
  label: "Divergence",
  kind: "gradient",
  description:
    "Branches: blue where the clade also exists in the other tree, yellow where its leaves are scattered, grey on a leaf",
  column: "",
  categories: [],
  // A leaf always matches itself: its branch says nothing.
  min_leaves: 2,
};

/** The ways a metric's comparison can be coloured, in the order to offer them. */
export function presentationsOf(
  metric: string,
  metrics: readonly MetricSummary[] | undefined,
): Presentation[] {
  const declared = metrics?.find((m) => m.name === metric)?.presentations;
  return declared && declared.length > 0 ? declared : [DIVERGENCE];
}

/**
 * The presentation actually shown, or null for the trees in black.
 *
 * "" asks for the metric's first. A name the metric does not offer — a link
 * made under another metric — also opens with its first, rather than with
 * nothing: the person asked for colour, and none would read as "nothing
 * differs".
 */
export function shownPresentation(
  colour: string,
  presentations: readonly Presentation[],
): Presentation | null {
  if (colour === "none") return null;
  return presentations.find((p) => p.name === colour) ?? presentations[0] ?? null;
}

/** The metric's title, for the list and the header; its name before /metrics answers. */
export function metricTitle(metric: string, metrics: readonly MetricSummary[] | undefined): string {
  return metrics?.find((m) => m.name === metric)?.title ?? metric;
}

/** The header's number, from the comparison's own metric. */
export function headline(
  summary: ComparisonSummary,
  manifest?: MetricSummary,
): {
  label: string;
  title: string;
  value: number;
  normalised?: number;
  of?: number;
  /** Set when the number is a range, `value` to `to` — SPR when not exact (§53). */
  to?: number;
} | null {
  const scalars = summary.summary;
  if (scalars.rf !== undefined) {
    return {
      label: "RF",
      // Spelled out because the number alone is ambiguous: implementations
      // differ by a factor of two on exactly this quantity. The server reports
      // the full symmetric difference, as DendroPy and ETE3 do, and the
      // normalised figure beside it is a fraction of the maximum for these two
      // trees, so 1 means no clade in common.
      title:
        "Robinson-Foulds distance: clades in one tree but not the other, " +
        "counted in both directions",
      value: Number(scalars.rf),
      normalised: scalars.rf_normalised !== undefined ? Number(scalars.rf_normalised) : undefined,
    };
  }
  if (scalars.triplet !== undefined) {
    return { label: "Triplet", title: "Triplet distance", value: Number(scalars.triplet) };
  }
  // Any other metric: the scalar its manifest names, or the first it declares.
  const declared = manifest?.outputs?.summary ?? [];
  const key = manifest?.headline?.key ?? declared.find((s) => scalars[s.key] !== undefined)?.key;
  if (!key || scalars[key] === undefined) return null;
  const spec = declared.find((s) => s.key === key);
  const whole = manifest?.headline?.of;
  const upTo = manifest?.headline?.to;
  const value = Number(scalars[key]);
  const to = upTo && scalars[upTo] !== undefined ? Number(scalars[upTo]) : undefined;
  return {
    label: spec?.label || key,
    title: spec?.description || manifest?.title || key,
    value,
    of: whole && scalars[whole] !== undefined ? Number(scalars[whole]) : undefined,
    // A range only while the bounds differ: an exact value is one number.
    to: to !== undefined && to !== value ? to : undefined,
  };
}

/**
 * Which nodes a gradient presentation has nothing to say about, or undefined
 * when it scores every node: those with fewer leaves than it declares (§52).
 * A leaf always matches itself, a clade of two holds no triple; drawn on the
 * ramp they would read as agreement nobody measured.
 */
export function unmeasuredBy(
  shown: Pick<Presentation, "kind" | "min_leaves"> | null,
): ((node: { metadata?: Record<string, unknown> }) => boolean) | undefined {
  const floor = shown?.kind === "gradient" ? (shown.min_leaves ?? 1) : 1;
  if (floor <= 1) return undefined;
  return (node) => Number(node.metadata?.trueLeafCount ?? 1) < floor;
}

/** What the legend calls those nodes. */
export function unmeasuredLabel(shown: Pick<Presentation, "min_leaves">): string {
  const floor = shown.min_leaves ?? 1;
  return floor === 2 ? "A leaf: nothing to measure" : `Under ${floor} leaves: nothing to measure`;
}
