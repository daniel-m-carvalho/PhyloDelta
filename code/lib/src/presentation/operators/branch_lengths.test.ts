// @vitest-environment jsdom
/**
 * Branch lengths written beside the branches (§44).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BranchLengthPresenter, formatBranchLength } from "./branch_lengths";
import { makeHarness, namedTree } from "./harness";

describe("formatBranchLength", () => {
  it("writes up to three decimals, without trailing zeros", () => {
    expect(formatBranchLength(0.5)).toBe("0.5");
    expect(formatBranchLength(1.23456)).toBe("1.235");
    expect(formatBranchLength(12)).toBe("12");
    expect(formatBranchLength(0.0019524665)).toBe("0.002");
    expect(formatBranchLength(0)).toBe("0");
  });

  it("does not round a very short branch down to a claim of no length", () => {
    expect(formatBranchLength(0.0003)).toBe("<0.001");
    expect(formatBranchLength(-0.0003)).toBe(">-0.001");
    expect(formatBranchLength(-0.25)).toBe("-0.25");
  });
});

describe("BranchLengthPresenter", () => {
  // jsdom has no canvas: a stand-in records what would be written, and
  // `measure` says how wide a label is, which decides whether it fits.
  let written: string[];
  let measure: number;
  beforeEach(() => {
    written = [];
    measure = 10;
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
      () =>
        ({
          setTransform() {},
          clearRect() {},
          measureText: () => ({ width: measure }),
          fillText: (text: string) => written.push(text),
        }) as unknown as CanvasRenderingContext2D,
    );
  });
  afterEach(() => vi.restoreAllMocks());

  function mounted(enabled: boolean) {
    const h = makeHarness(namedTree());
    Object.defineProperty(h.container, "clientWidth", { value: 1000 });
    Object.defineProperty(h.container, "clientHeight", { value: 1000 });
    // The harness maps graph coordinates to pixels one to one, and tree y runs
    // negative: place the tree on screen as a real camera would.
    const renderer = h.viewer.getRenderer() as unknown as {
      graphToViewport: (p: { x: number; y: number }) => { x: number; y: number };
    };
    renderer.graphToViewport = ({ x, y }) => ({ x: x * 8, y: 500 + y * 4 });
    const lengths = new BranchLengthPresenter({ enabled });
    lengths.attach(h.viewer);
    h.render();
    return { h, lengths };
  }

  it("writes nothing until it is switched on", () => {
    const { lengths } = mounted(false);
    expect(written).toEqual([]);
    lengths.setEnabled(true);
    expect(written.length).toBeGreaterThan(0);
  });

  it("writes each branch's length, from the edge that draws the branch", () => {
    mounted(true);
    // namedTree: a, b, c and d each have length 1.
    expect(written).toEqual(["1", "1", "1", "1"]);
  });

  it("leaves a branch bare when its label would not fit beside it", () => {
    // Wider than any branch is drawn: nothing may be written over its
    // neighbours instead.
    measure = 5000;
    const { lengths } = mounted(true);
    expect(written).toEqual([]);
    expect(lengths.drawnCount()).toBe(0);
  });

  it("does not print a label over another where rows sit closer than a line", () => {
    // Squash the tree vertically: every row within a few pixels of the next.
    const h = makeHarness(namedTree());
    Object.defineProperty(h.container, "clientWidth", { value: 1000 });
    Object.defineProperty(h.container, "clientHeight", { value: 1000 });
    const renderer = h.viewer.getRenderer() as unknown as {
      graphToViewport: (p: { x: number; y: number }) => { x: number; y: number };
    };
    renderer.graphToViewport = ({ x, y }) => ({ x: x * 8, y: 500 + y * 0.02 });
    const lengths = new BranchLengthPresenter({ enabled: true });
    lengths.attach(h.viewer);
    h.render();
    // c and d share the same x span and sit a hair apart: only one of them.
    expect(lengths.drawnCount()).toBeLessThan(4);
    expect(lengths.drawnCount()).toBeGreaterThan(0);
  });

  it("clears its labels when switched off", () => {
    const { lengths } = mounted(true);
    written = [];
    lengths.setEnabled(false);
    expect(written).toEqual([]);
    expect(lengths.drawnCount()).toBe(0);
  });
});
