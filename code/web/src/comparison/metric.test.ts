import { describe, expect, it } from "vitest";

import type { ComparisonSummary, MetricSummary } from "../api/types";
import {
  DEFAULT_LEGEND,
  gradientLegend,
  headline,
  isEntry,
  presentationsOf,
  shownPresentation,
  unmeasuredBy,
  unmeasuredLabel,
  viewMetric,
} from "./metric";

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

describe("one comparison, one metric (§52)", () => {
  // Built as the server describes a metric. The names are invented on purpose:
  // what is offered must come from the declaration, not from a list here.
  const gradient = { name: "branches", label: "Share kept", kind: "gradient" as const, description: "", column: "", categories: [] };
  const leaves = {
    name: "leaves", label: "Kept or moved", kind: "categories" as const, description: "",
    column: "moved", categories: ["Kept", "Moved"],
  };
  const metric = (name: string, extra: Partial<MetricSummary> = {}): MetricSummary => ({
    name, title: `${name} title`, description: "", kind: "python", available: true,
    version: "1", capabilities: {}, ...extra,
  });
  const metrics = [
    metric("rf"),
    metric("quillwort", {
      presentations: [gradient, leaves],
      headline: { key: "moved", of: "n_leaves" },
      outputs: { summary: [{ key: "moved", label: "Moved", description: "Leaves that moved" }], columns: [] },
    }),
  ];

  it("names the metric each listing entry is by", () => {
    expect(viewMetric({ metrics: ["rf", "quillwort"], metric: "quillwort" })).toBe("quillwort");
    // A server from before §52 sends no `metric`: RF where computed, as before.
    expect(viewMetric({ metrics: ["quillwort", "rf"] })).toBe("rf");
  });

  it("finds the entry a link names, by pair and metric", () => {
    const entry = { id: "a__b", metrics: ["rf", "quillwort"], metric: "quillwort" };
    expect(isEntry(entry, "a__b", "quillwort")).toBe(true);
    expect(isEntry(entry, "a__b", "rf")).toBe(false);
    // A link without a metric opens the first of the pair's entries.
    expect(isEntry(entry, "a__b", null)).toBe(true);
  });

  it("offers exactly the presentations the metric declares", () => {
    expect(presentationsOf("quillwort", metrics).map((p) => p.name)).toEqual(["branches", "leaves"]);
    // A metric that declares none, or before /metrics answers: the divergence gradient.
    expect(presentationsOf("rf", metrics).map((p) => p.name)).toEqual(["divergence"]);
    expect(presentationsOf("quillwort", undefined).map((p) => p.name)).toEqual(["divergence"]);
  });

  it("shows the one asked for, the first for a name it does not offer, and none for none", () => {
    const offered = presentationsOf("quillwort", metrics);
    expect(shownPresentation("leaves", offered)?.name).toBe("leaves");
    expect(shownPresentation("", offered)?.name).toBe("branches");
    // A link made under another metric: its colouring is not offered here.
    expect(shownPresentation("divergence", offered)?.name).toBe("branches");
    expect(shownPresentation("none", offered)).toBeNull();
  });

  it("heads a comparison known only within bounds with the range, and an exact one with its value", () => {
    const ranged = metric("bounded", {
      headline: { key: "lower", of: "", to: "upper" },
      outputs: { summary: [{ key: "lower", label: "SPR distance", description: "" }], columns: [] },
    });
    const at = (scalars: Record<string, number>) =>
      headline({ summary: scalars } as unknown as ComparisonSummary, ranged);
    expect(at({ lower: 1905, upper: 5653 })).toMatchObject({ label: "SPR distance", value: 1905, to: 5653 });
    expect(at({ lower: 3, upper: 3 })?.to).toBeUndefined();
  });

  it("heads the comparison with the scalar the metric names, and what it is out of", () => {
    const summary = { summary: { moved: 14736, n_leaves: 17645 } } as unknown as ComparisonSummary;
    expect(headline(summary, metrics[1])).toMatchObject({ label: "Moved", value: 14736, of: 17645 });
  });
});

describe("unmeasuredBy", () => {
  const node = (leaves: number) => ({ metadata: { trueLeafCount: leaves } });

  it("marks clades too small for the score to say anything", () => {
    const triplet = unmeasuredBy({ kind: "gradient", min_leaves: 3 })!;
    expect([1, 2, 3, 40].map((n) => triplet(node(n)))).toEqual([true, true, false, false]);
    expect(unmeasuredLabel({ min_leaves: 3 })).toBe("Under 3 leaves: nothing to measure");
  });

  it("greys the leaves under the shared one, before /metrics answers too", () => {
    const divergence = unmeasuredBy(presentationsOf("rf", undefined)[0])!;
    expect(divergence(node(1))).toBe(true);
    expect(divergence(node(2))).toBe(false);
    expect(unmeasuredLabel({ min_leaves: 2 })).toBe("A leaf: nothing to measure");
  });

  it("marks nothing where every node is scored, or the leaves are painted instead", () => {
    expect(unmeasuredBy({ kind: "gradient", min_leaves: 1 })).toBeUndefined();
    expect(unmeasuredBy({ kind: "gradient" })).toBeUndefined();
    expect(unmeasuredBy({ kind: "categories", min_leaves: 3 })).toBeUndefined();
    expect(unmeasuredBy(null)).toBeUndefined();
  });
});

describe("gradientLegend", () => {
  it("uses the metric's own words for the ends of the bar when it declares two", () => {
    expect(gradientLegend({ legend: ["Same score", "Far apart"] })).toEqual(["Same score", "Far apart"]);
  });

  it("falls back to the shared correspondence's words otherwise", () => {
    expect(gradientLegend(undefined)).toEqual(DEFAULT_LEGEND);
    expect(gradientLegend({})).toEqual(["Identical", "Diverged"]);
    expect(gradientLegend({ legend: [] })).toEqual(DEFAULT_LEGEND);
    expect(gradientLegend({ legend: ["one"] })).toEqual(DEFAULT_LEGEND);
  });
});
