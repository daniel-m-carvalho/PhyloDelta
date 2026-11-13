/**
 * What the app says about a re-root (§56), kept apart from the view so it can
 * be tested without one.
 */

import type { ComparisonStatus, ComparisonSummary, MetricSummary, RerootInfo } from "../api/types";
import { headline } from "./metric";

/** A build's state, in the words the header uses. */
export function rebuildLabel(status: ComparisonStatus["status"] | undefined): string {
  switch (status) {
    case "running":
      return "computing";
    case "ready":
      return "ready";
    case "failed":
      return "failed";
    default:
      return "pending";
  }
}

/**
 * The header's number as it was before the re-root, read from what the server
 * kept on the new comparison's row — so it is there even when the original was
 * replaced. Null when the original had no result for this metric.
 */
export function headlineBefore(
  summary: ComparisonSummary | null,
  manifest: MetricSummary | undefined,
  info: RerootInfo | null | undefined,
  metric: string | null,
): ReturnType<typeof headline> {
  if (!summary || !info || !metric) return null;
  const before = info.before?.[metric];
  if (!before) return null;
  return headline({ ...summary, summary: before }, manifest);
}

/** "the left tree" / "the right tree", or its name. */
export function sideName(side: 0 | 1, names?: { left: string; right: string }): string {
  if (!names) return side === 0 ? "the left tree" : "the right tree";
  return side === 0 ? names.left : names.right;
}
