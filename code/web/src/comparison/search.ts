/**
 * One search box, two trees (§37).
 *
 * Each tree is searched on its own and the answers are merged here into one
 * list keyed by label, so every row says where that name exists before the
 * user picks it. A name in one tree only is a row like any other, marked
 * absent on the side that does not have it — which is the finding, not an
 * error.
 */

import type { NodeMatch, NodeSearch } from "../api/types";

export interface SearchRow {
  /** As stored. Rows are merged case-insensitively, as the server matches. */
  label: string;
  exact: boolean;
  /**
   * The nodes carrying this label on each side, empty where it is absent.
   * More than one is possible for an internal label; leaves are unique.
   */
  sides: [NodeMatch[], NodeMatch[]];
}

/**
 * Merge two trees' answers into rows, in the order the server ranks them:
 * exact first, then shortest, then alphabetical.
 *
 * Either side may be null — that tree's request failed. Its column then reads
 * as unknown rather than as absent; see {@link SearchResult.failed}.
 */
export function mergeByLabel(left: NodeSearch | null, right: NodeSearch | null): SearchRow[] {
  const rows = new Map<string, SearchRow>();
  ([left, right] as const).forEach((answer, side) => {
    for (const match of answer?.matches ?? []) {
      const key = match.label.toLowerCase();
      let row = rows.get(key);
      if (!row) {
        row = { label: match.label, exact: match.exact, sides: [[], []] };
        rows.set(key, row);
      }
      row.sides[side].push(match);
    }
  });
  return [...rows.values()].sort(
    (a, b) =>
      Number(b.exact) - Number(a.exact) ||
      a.label.length - b.label.length ||
      a.label.localeCompare(b.label),
  );
}

/**
 * What both trees said, together.
 *
 * `total` is per side because each list is capped at the server's `limit`:
 * the rows can show 20 names while vibrio-upgma has 8,758 starting with `1`.
 */
export interface SearchResult {
  query: string;
  rows: SearchRow[];
  totals: [number, number];
  /** Why a side could not be searched, if it could not. Never read as "absent". */
  failed: [string | null, string | null];
}

/**
 * The sentence a panel shows when the picked name is not in its tree.
 *
 * Says which tree, and that the view did not move, because the other panel
 * did: without that, a panel that stayed still reads as a panel that broke.
 */
export function absentFrom(label: string, treeName: string): string {
  return `${label} is not in ${treeName}. This panel has not moved.`;
}
