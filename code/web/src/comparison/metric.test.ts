import { describe, expect, it } from "vitest";

import type { ComparisonSummary } from "../api/types";
import { hasMovedLeaves, headline, movedLeavesMissing, presentation, sliceMetric, viewMetric } from "./metric";

describe("viewMetric", () => {
  it("reads a comparison under the metric it was computed with", () => {
    // The case that used to open to a 404: asking for rf regardless.
    expect(viewMetric({ metrics: ["triplet"] })).toBe("triplet");
    expect(viewMetric({ metrics: ["rf-treediff"] })).toBe("rf-treediff");
  });

  it("prefers rf where it was computed", () => {
    expect(viewMetric({ metrics: ["triplet", "rf"] })).toBe("rf");
  });

  it("falls back to rf only when the comparison names none", () => {
    expect(viewMetric({ metrics: [] })).toBe("rf");
  });
});

describe("headline", () => {
  const summary = (scalars: Record<string, number>) =>
    ({ summary: scalars }) as unknown as ComparisonSummary;

  it("shows RF, normalised where reported", () => {
    expect(headline(summary({ rf: 12, rf_normalised: 0.25 }))).toMatchObject({
      label: "RF", value: 12, normalised: 0.25,
    });
  });

  it("shows the triplet distance for a triplet comparison", () => {
    expect(headline(summary({ triplet: 40 }))).toMatchObject({ label: "Triplet", value: 40 });
  });

  it("shows nothing rather than an invented number", () => {
    expect(headline(summary({}))).toBeNull();
  });
});

describe("moved leaves (§46)", () => {
  const withMast = { metrics: ["mast", "rf"] };
  const without = { metrics: ["rf"] };

  it("are offered only where the comparison computed them", () => {
    expect(hasMovedLeaves(withMast)).toBe(true);
    expect(hasMovedLeaves(without)).toBe(false);
  });

  it("ride along in the slices, without changing the metric the header reads", () => {
    // The gradient comes from correspondence under any metric, so asking
    // slices under mast costs it nothing and brings the moved counts.
    expect(sliceMetric(withMast)).toBe("mast");
    expect(viewMetric(withMast)).toBe("rf");
    expect(sliceMetric(without)).toBe("rf");
  });

  it("show one presentation at a time", () => {
    expect(presentation({ gradient: true, moved: false }, withMast)).toBe("divergence");
    expect(presentation({ gradient: false, moved: true }, withMast)).toBe("moved");
    expect(presentation({ gradient: false, moved: false }, withMast)).toBe("none");
  });

  it("fall back to the gradient, not to nothing, where they were not computed", () => {
    // The bug: a link with mv=1 to a comparison without them opened uncoloured,
    // which reads as "nothing differs".
    expect(presentation({ gradient: false, moved: true }, without)).toBe("divergence");
  });
});

describe("movedLeavesMissing", () => {
  it("says not computed before /status answers, and when nothing failed", () => {
    expect(movedLeavesMissing()).toBe("Not computed for this comparison");
    expect(movedLeavesMissing({ metrics_failed: {} })).toBe("Not computed for this comparison");
  });

  it("gives the server's reason when MAST was declined", () => {
    expect(movedLeavesMissing({ metrics_failed: { mast: "declined: too big" } })).toBe(
      "Not available: declined: too big",
    );
  });

  it("says a failed /status failed, rather than hiding that a reason was lost", () => {
    expect(movedLeavesMissing(new Error("Request failed (502)"))).toBe(
      "Not computed for this comparison; the reason could not be fetched (Request failed (502))",
    );
  });
});
