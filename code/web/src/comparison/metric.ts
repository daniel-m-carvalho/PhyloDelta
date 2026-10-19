/**
 * Which metric to read a comparison under.
 *
 * A comparison is computed with the metric its uploader chose, and the server
 * refuses any other by name (404, "unknown metric"). Asking for "rf" regardless
 * worked only while every comparison had RF; one computed with Triplet alone
 * would open to an error. RF stays the preference where it was computed,
 * because the catalogue pairs carry it and the gradient reads most directly
 * against it.
 */

import type { ComparisonSummary, PairSummary } from "../api/types";

export function viewMetric(pair: Pick<PairSummary, "metrics">): string {
  if (pair.metrics.includes("rf")) return "rf";
  return pair.metrics[0] ?? "rf";
}

/** Whether the comparison carries moved leaves, so the view can be offered (§46). */
export function hasMovedLeaves(pair: Pick<PairSummary, "metrics">): boolean {
  return pair.metrics.includes("mast");
}

/** What colours the trees: one presentation at a time (§46). */
export type Presentation = "divergence" | "moved" | "none";

/**
 * The presentation actually shown, from what was asked for and what exists.
 *
 * Moved leaves asked for on a comparison without them — an old link, a shared
 * one, a comparison that declined the metric — falls back to the divergence
 * gradient rather than to nothing: the person asked for colour, and "no
 * colour" would read as "nothing differs".
 */
export function presentation(
  options: { gradient: boolean; moved: boolean },
  pair: Pick<PairSummary, "metrics">,
): Presentation {
  if (options.moved) return hasMovedLeaves(pair) ? "moved" : "divergence";
  return options.gradient ? "divergence" : "none";
}

/**
 * Which metric to ask slices under.
 *
 * A slice carries the per-node columns of the metric it was asked for, and
 * only those. The gradient does not depend on it — similarity comes from the
 * pair's correspondence, served with every metric — so asking under `mast`
 * where it exists brings the moved-leaf counts along with the same gradient,
 * and switching between the two presentations costs no request. Nothing here
 * reads RF's own column (`exact`).
 */
export function sliceMetric(pair: Pick<PairSummary, "metrics">): string {
  return hasMovedLeaves(pair) ? "mast" : viewMetric(pair);
}

/** The header's number: RF where the metric reports it, else the metric's own. */
export function headline(
  summary: ComparisonSummary,
): { label: string; title: string; value: number; normalised?: number } | null {
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
  return null;
}
