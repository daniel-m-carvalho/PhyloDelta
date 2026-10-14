/**
 * Where a metric's implementation comes from, shown where the metric is
 * offered (§42): what a user picking a metric wants to know is whose
 * computation they are getting.
 */

import type { MetricReference } from "../api/types";

export function MetricReferenceLine({ reference }: { reference: MetricReference | null }) {
  if (!reference) return null;
  return (
    <p className="metric-references">
      <span className="metric-reference-role">Computed as in</span> {reference.citation}
      {reference.url ? (
        <>
          {" "}
          <a href={reference.url} target="_blank" rel="noreferrer">
            {reference.doi ? `doi:${reference.doi}` : reference.url.replace(/^https:\/\//, "")}
          </a>
        </>
      ) : null}
    </p>
  );
}
