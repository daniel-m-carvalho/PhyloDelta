/**
 * The papers a metric rests on, where the metric is offered (§42).
 *
 * Each says what it is the reference *for*: a metric computed by someone
 * else's program has two papers — the one defining the metric and the one
 * describing how it is computed — and listing them unlabelled would leave the
 * reader to guess which is which.
 */

import type { MetricReference } from "../api/types";

const ROLE: Record<MetricReference["role"], string> = {
  metric: "Defined in",
  implementation: "Computed as in",
};

export function MetricReferences({ references }: { references: MetricReference[] }) {
  if (references.length === 0) return null;
  return (
    <ul className="metric-references">
      {references.map((reference) => (
        <li key={`${reference.role}:${reference.citation}`}>
          <span className="metric-reference-role">{ROLE[reference.role] ?? reference.role}</span>{" "}
          {reference.citation}
          {reference.url ? (
            <>
              {" "}
              <a href={reference.url} target="_blank" rel="noreferrer">
                doi:{reference.doi}
              </a>
            </>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
