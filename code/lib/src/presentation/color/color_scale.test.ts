import { describe, expect, it } from "vitest";
import {
  CategoricalColorScale,
  DEFAULT_PALETTE,
  DIFF_PALETTE,
  SequentialColorScale,
} from "./color_scale";

describe("CategoricalColorScale", () => {
  it("assigns a stable color per key", () => {
    const scale = new CategoricalColorScale();
    const first = scale.color("PT");
    expect(scale.color("PT")).toBe(first); // memoized, not re-rolled
  });

  it("walks the palette in order for new keys", () => {
    const scale = new CategoricalColorScale(["#a", "#b", "#c"]);
    expect(scale.color("x")).toBe("#a");
    expect(scale.color("y")).toBe("#b");
    expect(scale.color("z")).toBe("#c");
  });

  it("wraps around when the palette is exhausted", () => {
    const scale = new CategoricalColorScale(["#a", "#b"]);
    scale.color("x");
    scale.color("y");
    expect(scale.color("z")).toBe("#a");
  });

  it("gives the same key the same color across shared views", () => {
    // The reason to share ONE instance between two side-by-side trees.
    const shared = new CategoricalColorScale();
    const leftFirst = shared.color("ES"); // left panel draws ES first
    shared.color("FR");
    expect(shared.color("ES")).toBe(leftFirst); // right panel agrees
  });

  it("falls back to the default palette when given an empty one", () => {
    const scale = new CategoricalColorScale([]);
    expect(DEFAULT_PALETTE).toContain(scale.color("x"));
  });

  it("primes keys in a stable order", () => {
    const scale = new CategoricalColorScale(["#a", "#b", "#c"]);
    scale.prime(["one", "two"]);
    expect(scale.assignments().get("one")).toBe("#a");
    expect(scale.assignments().get("two")).toBe("#b");
  });

  it("assignments() reads without assigning", () => {
    // color() assigns on miss, so a legend built from it could recolor the very
    // chart it describes. assignments() must never mutate.
    const scale = new CategoricalColorScale(["#a", "#b"]);
    scale.color("seen");

    const snapshot = scale.assignments();
    expect(snapshot.size).toBe(1);
    expect(snapshot.has("unseen")).toBe(false);
    expect(scale.color("next")).toBe("#b"); // "unseen" never consumed a slot
  });

  it("returns a detached snapshot, not the live map", () => {
    const scale = new CategoricalColorScale();
    scale.color("a");
    const snapshot = scale.assignments();
    scale.color("b");
    expect(snapshot.size).toBe(1);
  });
});

describe("SequentialColorScale", () => {
  it("maps the domain ends to the first and last stop", () => {
    const scale = new SequentialColorScale({ stops: ["#000000", "#ffffff"] });
    expect(scale.color(0)).toBe("#000000");
    expect(scale.color(1)).toBe("#ffffff");
  });

  it("interpolates between stops", () => {
    const scale = new SequentialColorScale({ stops: ["#000000", "#ffffff"] });
    expect(scale.color(0.5)).toBe("#808080");
  });

  it("clamps values outside the domain", () => {
    const scale = new SequentialColorScale({ stops: ["#000000", "#ffffff"] });
    expect(scale.color(-10)).toBe("#000000");
    expect(scale.color(10)).toBe("#ffffff");
  });

  it("honours a custom domain", () => {
    const scale = new SequentialColorScale({
      stops: ["#000000", "#ffffff"],
      domain: [0, 100],
    });
    expect(scale.getDomain()).toEqual([0, 100]);
    expect(scale.color(50)).toBe("#808080");
  });

  it("survives a zero-width domain without dividing by zero", () => {
    const scale = new SequentialColorScale({
      stops: ["#000000", "#ffffff"],
      domain: [5, 5],
    });
    expect(scale.color(5)).toBe("#000000");
  });

  it("defaults to DIFF_PALETTE and exposes its stops for a legend", () => {
    const scale = new SequentialColorScale();
    expect(scale.stopsHex()).toEqual(DIFF_PALETTE.map((c) => c.toLowerCase()));
  });

  it("ignores a stop list too short to interpolate", () => {
    const scale = new SequentialColorScale({ stops: ["#123456"] });
    expect(scale.stopsHex().length).toBeGreaterThan(1);
  });
});

describe("CategoricalColorScale — a colour chosen for one category", () => {
  it("wins over the palette for that key only", () => {
    const scale = new CategoricalColorScale(["#111111", "#222222", "#333333"]);
    scale.prime(["Animal", "Food", "Human"]);
    scale.setColor("Human", "#e03131");
    expect(scale.color("Human")).toBe("#e03131");
    expect(scale.color("Animal")).toBe("#111111");
    expect(scale.color("Food")).toBe("#222222");
    expect(scale.assignments().get("Human")).toBe("#e03131");
  });

  it("gives the key back its own palette colour when cleared", () => {
    const scale = new CategoricalColorScale(["#111111", "#222222", "#333333"]);
    scale.prime(["Animal", "Food", "Human"]);
    scale.setColor("Food", "#e03131");
    scale.clearColor("Food");
    expect(scale.color("Food")).toBe("#222222");
  });

  it("does not shift other keys' palette colours, even when chosen before it was seen", () => {
    // A choice from a shared link arrives before any bar is drawn. The key
    // still takes its palette slot, so the keys after it keep theirs and a
    // reset gives it the colour it would always have had.
    const plain = new CategoricalColorScale(["#111111", "#222222", "#333333"]);
    plain.prime(["Animal", "Food", "Human"]);
    const picked = new CategoricalColorScale(["#111111", "#222222", "#333333"]);
    picked.setColor("Animal", "#e03131");
    picked.prime(["Animal", "Food", "Human"]);

    expect(picked.color("Food")).toBe(plain.color("Food"));
    expect(picked.color("Human")).toBe(plain.color("Human"));
    picked.clearColors();
    expect(picked.color("Animal")).toBe(plain.color("Animal"));
  });

  it("lists what was chosen", () => {
    const scale = new CategoricalColorScale();
    scale.setColor("Human", "#e03131");
    expect([...scale.chosenColors()]).toEqual([["Human", "#e03131"]]);
    scale.clearColors();
    expect(scale.chosenColors().size).toBe(0);
  });
});
