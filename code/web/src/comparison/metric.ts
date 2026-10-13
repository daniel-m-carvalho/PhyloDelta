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
