import { describe, expect, it } from "vitest";

import { markAction, type Placed } from "./markPlacement";

const placed = (over: Partial<Placed> = {}): Placed => ({
  arrival: 15544,
  label: "1203",
  shown: true,
  slice: "slice-A",
  ...over,
});

describe("markAction", () => {
  it("flashes a new arrival", () => {
    expect(markAction(null, 15544, "slice-A")).toBe("flash");
    expect(markAction(placed({ arrival: 8857 }), 15544, "slice-A")).toBe("flash");
  });

  it("leaves a panel alone when only the other panel's slice changed", () => {
    // The bug: a search found 1203 in both trees, the left slice came back
    // first and started blinking, then the right one arrived — and the effect,
    // running for both panels, re-placed the left mark and stopped its blink.
    expect(markAction(placed(), 15544, "slice-A")).toBe("keep");
  });

  it("moves the mark quietly when this panel's own slice changed", () => {
    // Back, or a resize: the same leaf, drawn as a different node.
    expect(markAction(placed(), 15544, "slice-B")).toBe("move");
  });

  it("does not bring back a mark a jump into the other panel took", () => {
    expect(markAction(placed({ shown: false }), 15544, "slice-B")).toBe("keep");
  });
});
