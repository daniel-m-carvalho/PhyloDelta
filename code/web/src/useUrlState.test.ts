/**
 * The URL names what is on screen.
 *
 * Tested because the failure is silent and annoying rather than loud: a
 * refresh quietly dropping you back at the chooser looks like a design choice
 * until you have lost a view of two 500k-leaf trees for the third time.
 */

import { beforeEach, describe, expect, it } from "vitest";
import { act, renderHook } from "./test_support/renderHook";
import { DEFAULT_OPTIONS, useUrlState } from "./useUrlState";

describe("view state in the URL", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("starts empty when the URL names nothing", () => {
    const { result } = renderHook(() => useUrlState());
    expect(result.current[0].comparison).toBeNull();
  });

  it("round-trips a comparison and both navigation paths", () => {
    const { result } = renderHook(() => useUrlState());
    act(() => result.current[1]({ comparison: "a__b", left: [3, 900], right: [12] }));

    expect(window.location.hash).toBe("#/c/a__b?l=3%2C900&r=12");

    const restored = renderHook(() => useUrlState());
    expect(restored.result.current[0]).toEqual({
      comparison: "a__b",
      left: [3, 900],
      right: [12],
      options: DEFAULT_OPTIONS,
    });
  });

  it("omits empty paths rather than writing them", () => {
    const { result } = renderHook(() => useUrlState());
    act(() => result.current[1]({ comparison: "a__b", left: [], right: [] }));
    expect(window.location.hash).toBe("#/c/a__b");
  });

  it("encodes an id safely", () => {
    const { result } = renderHook(() => useUrlState());
    act(() => result.current[1]({ comparison: "a/b?c", left: [], right: [] }));
    const restored = renderHook(() => useUrlState());
    expect(restored.result.current[0].comparison).toBe("a/b?c");
  });

  it("ignores a hash it does not understand", () => {
    window.history.replaceState(null, "", "#something-else");
    const { result } = renderHook(() => useUrlState());
    expect(result.current[0].comparison).toBeNull();
  });

  it("round-trips the view options, writing only what differs from the default", () => {
    // The bug: the View menu remembered the choice and the URL did not, so a
    // refresh restored the navigation with the presentation reset under it.
    const { result } = renderHook(() => useUrlState());
    act(() =>
      result.current[1]({
        comparison: "a__b",
        left: [],
        right: [],
        options: {
          ...DEFAULT_OPTIONS,
          gradient: false,
          colorTarget: "clades",
          typing: true,
          columns: ["country", "year, collected"],
          cladeSizes: true,
          layout: "phylogram",
        },
      }),
    );

    const restored = renderHook(() => useUrlState()).result.current[0].options;
    expect(restored.gradient).toBe(false);
    expect(restored.colorTarget).toBe("clades");
    expect(restored.typing).toBe(true);
    // A column name may contain the separator any joined encoding would use.
    expect(restored.columns).toEqual(["country", "year, collected"]);
    expect(restored.cladeSizes).toBe(true);
    expect(restored.layout).toBe("phylogram");
    // Untouched defaults stay out of the URL.
    expect(window.location.hash).not.toContain("bs=");
  });

  it("round-trips colours chosen for categories, whatever the names contain (§43)", () => {
    const { result } = renderHook(() => useUrlState());
    const colors = { Human: "#e03131", "Source niche: Food. Raw": "#12b886" };
    act(() =>
      result.current[1]({
        comparison: "a__b", left: [], right: [],
        options: { ...DEFAULT_OPTIONS, colors },
      }),
    );
    expect(window.location.hash).toContain("cc=e03131.Human");

    const restored = renderHook(() => useUrlState());
    expect(restored.result.current[0].options.colors).toEqual(colors);
  });

  it("round-trips the branch-length options (§44)", () => {
    const { result } = renderHook(() => useUrlState());
    act(() =>
      result.current[1]({
        comparison: "a__b", left: [], right: [],
        options: { ...DEFAULT_OPTIONS, layout: "phylogram", lengths: true, lengthScale: "log" },
      }),
    );
    expect(window.location.hash).toContain("bl=1");
    expect(window.location.hash).toContain("ls=log");
    const restored = renderHook(() => useUrlState()).result.current[0].options;
    expect([restored.lengths, restored.lengthScale]).toEqual([true, "log"]);
  });

  it("drops a colour entry a browser could not paint", () => {
    window.history.replaceState(null, "", "#/c/a__b?cc=red.Human&cc=12b886.Food&cc=e03131");
    const { result } = renderHook(() => useUrlState());
    expect(result.current[0].options.colors).toEqual({ Food: "#12b886" });
  });

  it("writes no colours when none were chosen", () => {
    const { result } = renderHook(() => useUrlState());
    act(() => result.current[1]({ comparison: "a__b", left: [], right: [] }));
    expect(window.location.hash).not.toContain("cc=");
  });

  it("keeps the options when a write states only the navigation", () => {
    // Focusing a subtree must not silently reset the colouring.
    const { result } = renderHook(() => useUrlState());
    act(() =>
      result.current[1]({
        comparison: "a__b",
        left: [],
        right: [],
        options: { ...DEFAULT_OPTIONS, typing: true },
      }),
    );
    act(() => result.current[1]({ comparison: "a__b", left: [7], right: [] }));

    expect(result.current[0].options.typing).toBe(true);
    expect(result.current[0].left).toEqual([7]);
  });

  it("does not add a history entry per expansion", () => {
    // Otherwise Back would mean "undo one expand" rather than "leave this
    // comparison", and escaping a deep navigation would take twenty presses.
    const { result } = renderHook(() => useUrlState());
    const before = window.history.length;
    act(() => result.current[1]({ comparison: "a__b", left: [1], right: [] }));
    act(() => result.current[1]({ comparison: "a__b", left: [1, 2], right: [] }));
    act(() => result.current[1]({ comparison: "a__b", left: [1, 2, 3], right: [] }));
    expect(window.history.length).toBe(before);
  });

  it("round-trips moved leaves as one presentation, not beside the gradient (§46)", () => {
    const { result } = renderHook(() => useUrlState());
    act(() =>
      result.current[1]({
        comparison: "a__b",
        left: [],
        right: [],
        options: { ...DEFAULT_OPTIONS, gradient: false, moved: true },
      }),
    );
    expect(window.location.hash).toContain("mv=1");
    // Written once: mv implies the gradient is off, so g=0 would be noise.
    expect(window.location.hash).not.toContain("g=0");

    const restored = renderHook(() => useUrlState()).result.current[0].options;
    expect(restored.moved).toBe(true);
    expect(restored.gradient).toBe(false);
  });

  it("opens an old link, without mv, exactly as before", () => {
    window.history.replaceState(null, "", "/#/c/a__b?g=0");
    const options = renderHook(() => useUrlState()).result.current[0].options;
    expect(options.moved).toBe(false);
    expect(options.gradient).toBe(false);
  });
});
