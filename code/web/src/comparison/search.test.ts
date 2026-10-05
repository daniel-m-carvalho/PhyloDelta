import { describe, expect, it } from "vitest";

import type { NodeMatch, NodeSearch } from "../api/types";
import { absentFrom, mergeByLabel } from "./search";

const match = (label: string, node: number, exact = false): NodeMatch => ({
  node, label, exact, leaf: true, leaves: 1,
});
const answer = (...matches: NodeMatch[]): NodeSearch => ({
  tree: "t", query: "q", total: matches.length, exact: 0, matches,
});

describe("mergeByLabel", () => {
  it("gives a name one row, saying which trees have it", () => {
    const rows = mergeByLabel(
      answer(match("1203", 5, true), match("12030", 9)),
      answer(match("1203", 70, true), match("12031", 71)),
    );
    expect(rows.map((row) => [row.label, row.sides[0].length, row.sides[1].length])).toEqual([
      ["1203", 1, 1],
      ["12030", 1, 0],
      ["12031", 0, 1],
    ]);
    // Each side keeps its own id: the two trees number their nodes separately.
    expect(rows[0].sides.map((side) => side[0].node)).toEqual([5, 70]);
  });

  it("puts the exact name first, then shortest, then alphabetical", () => {
    const rows = mergeByLabel(
      answer(match("1200", 1), match("120", 2), match("12", 3, true)),
      answer(match("121", 4)),
    );
    expect(rows.map((row) => row.label)).toEqual(["12", "120", "121", "1200"]);
  });

  it("treats a side whose request failed as unknown, not as empty of matches", () => {
    // mergeByLabel only sees no matches; the row records nothing there, and
    // `failed` is what stops the view reading that as "absent".
    const rows = mergeByLabel(answer(match("7", 1, true)), null);
    expect(rows).toHaveLength(1);
    expect(rows[0].sides[1]).toEqual([]);
  });
});

describe("absentFrom", () => {
  it("names the tree and says the panel stayed where it was", () => {
    expect(absentFrom("1203", "vibrio-nj")).toBe(
      "1203 is not in vibrio-nj. This panel has not moved.",
    );
  });
});
