/**
 * Saying how an uploaded isolate table met its tree (§47).
 *
 * The server matches exactly, after trimming, and reports what did not match
 * instead of guessing; these turn that report into the line a person reads.
 * The counts are the point: "312 rows match no leaf (e.g. 1234_1, …)" is how
 * a near miss — or the wrong column — shows itself.
 */

import type { IsolateJoinReport } from "../api/types";

type Side = "left" | "right";
const SIDE: Record<Side, string> = { left: "Left", right: "Right" };

function plural(n: number, one: string, many: string): string {
  return `${n.toLocaleString()} ${n === 1 ? one : many}`;
}

/** One side's join, in a sentence. */
export function describeJoin(side: Side, report: IsolateJoinReport): string {
  if (report.error) return `${SIDE[side]} isolate data not used: ${report.error}`;
  const parts = [
    `${SIDE[side]}: ${plural(report.rows, "row", "rows")} joined on "${report.key_column}"`,
  ];
  if (report.rows_unmatched) {
    const examples = report.unmatched_examples.slice(0, 3).join(", ");
    const more = report.rows_unmatched > 3 || report.unmatched_examples.length > 3 ? ", …" : "";
    parts.push(
      `${plural(report.rows_unmatched, "matches", "match")} no leaf` +
        (examples ? ` (e.g. ${examples}${more})` : ""),
    );
  }
  if (report.rows_without_key) {
    parts.push(`${plural(report.rows_without_key, "has", "have")} no key`);
  }
  if (report.leaves_without_rows) {
    parts.push(
      `${plural(report.leaves_without_rows, "leaf has", "leaves have")} no rows`,
    );
  }
  return parts.join("; ");
}

/** Both sides, in order; empty when no table was uploaded. */
export function describeJoins(
  isolates: Partial<Record<Side, IsolateJoinReport>> | undefined,
): string[] {
  return (["left", "right"] as Side[]).flatMap((side) => {
    const report = isolates?.[side];
    return report ? [describeJoin(side, report)] : [];
  });
}

/** The sides whose table was not used, said as such. */
export function unusedTables(
  isolates: Partial<Record<Side, IsolateJoinReport>> | undefined,
): string[] {
  return (["left", "right"] as Side[]).flatMap((side) => {
    const report = isolates?.[side];
    return report?.error ? [describeJoin(side, report)] : [];
  });
}
