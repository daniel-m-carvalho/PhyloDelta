import { describe, expect, it } from "vitest";
import type { ComparisonSummary, RerootInfo } from "../api/types";
import { headlineBefore, rebuildLabel, sideName } from "./reroot";

const summary = { summary: { rf: 12, rf_normalised: 0.27 } } as unknown as ComparisonSummary;
const info: RerootInfo = {
  from: "a__b", side: "left", node: 7, label: "", replace: false,
  before: { rf: { rf: 0, rf_normalised: 0 } },
};

describe("a re-root in the header (§56)", () => {
  it("reads the number before from what the server kept, even with the original gone", () => {
    const before = headlineBefore(summary, undefined, info, "rf");
    expect(before?.label).toBe("RF");
    expect(before?.value).toBe(0);
  });

  it("says nothing for a comparison no re-root made, or a metric the original lacked", () => {
    expect(headlineBefore(summary, undefined, null, "rf")).toBeNull();
    expect(headlineBefore(summary, undefined, info, "triplet")).toBeNull();
    expect(headlineBefore(null, undefined, info, "rf")).toBeNull();
  });

  it("names the build's state as the header does", () => {
    const states = ["pending", "running", "ready", "failed", undefined] as const;
    expect(states.map((state) => rebuildLabel(state))).toEqual([
      "pending", "computing", "ready", "failed", "pending",
    ]);
  });

  it("names a side by its tree when it knows the names", () => {
    expect(sideName(0)).toBe("the left tree");
    expect(sideName(1, { left: "NJ", right: "UPGMA" })).toBe("UPGMA");
  });
});
