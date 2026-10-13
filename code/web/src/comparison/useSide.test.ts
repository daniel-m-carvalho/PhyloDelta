/**
 * How much detail to ask for.
 *
 * The budget is a property of the viewport, not a constant: asking the server
 * for more than the client can draw is this project's central failure in
 * miniature — the request succeeds, the bytes arrive, and the picture is
 * worse.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../api/client";
import type { TreeSlice } from "../api/types";
import { sliceCache } from "../api/sliceCache";
import { actAsync, renderHook } from "../test_support/renderHook";
import { DEFAULT_BUDGET, readableBudget, useSide } from "./useSide";

/**
 * Answer `slice({ around })` the way the server does (§40): ask the test's own
 * `ancestor` mock where to root, then its own `slice` mock for that root with
 * the node kept. A jump is one request now, and every test below goes on
 * saying what it said about where a jump lands and what it keeps.
 */
/** The smallest drawable slice, for tests where the slice is not what is under test. */
function bare(root = 0): TreeSlice {
  return {
    tree: "vibrio-upgma", root, budget: 50, displayed_leaves: 1, hidden_leaves: 0, total_leaves: 1,
    nodes: { id: [root], parent: [-1], label: ["x"], branch_len: [0], true_leaf_count: [1], truncated: [false] },
    comparison: null, kept: null,
  } as unknown as TreeSlice;
}

function mountPanel() {
  const slice = vi.mocked(api.slice);
  const answer = slice.getMockImplementation();
  if (answer) {
    slice.mockImplementation(async (tree, options = {}) => {
      if (options.around === undefined) return answer(tree, options);
      const { around, minLeaves, ...rest } = options;
      const context = await api.ancestor(tree, around, { minLeaves });
      const landed = await answer(tree, { ...rest, root: context.node, keep: around, around });
      return { ...landed, root: context.node };
    });
  }
  return renderHook(() => useSide("vibrio-upgma", "a__b"));
}

describe("readableBudget", () => {
  it("waits rather than guessing before the panel is measured", () => {
    // A placeholder budget would mean two slices per panel on every load:
    // one for a picture nobody sees, then the real one.
    expect(readableBudget(0)).toBe(0);
  });

  it("scales with the height available", () => {
    expect(readableBudget(600)).toBeLessThan(readableBudget(1200));
  });

  it("leaves enough pixels per leaf for the structure to be visible", () => {
    // The bug this replaced: a fixed 400 in a 577px panel is 1.4px a leaf, and
    // the terminals — which a cladogram pins to one column — fused into a
    // solid bar with a block of colour beside it.
    for (const height of [400, 577, 800, 1200]) {
      expect(height / readableBudget(height)).toBeGreaterThanOrEqual(5);
    }
  });

  it("is quantised, so settling layout does not cost a request", () => {
    // Measured on load: the panel reported 600px, then 577px. Both should ask
    // for the same slice.
    expect(readableBudget(600)).toBe(readableBudget(577));
  });

  it("stays usable in a very small or very large window", () => {
    expect(readableBudget(50)).toBeGreaterThanOrEqual(40);
    expect(readableBudget(20_000)).toBeLessThanOrEqual(600);
  });

  it("has a default for the unmeasured case that is itself readable", () => {
    expect(DEFAULT_BUDGET).toBeGreaterThan(40);
    expect(DEFAULT_BUDGET).toBeLessThan(600);
  });
});

describe("arriving from the other panel", () => {
  const leaf = 3296;

  function runJump(ancestor: typeof api.ancestor) {
    vi.spyOn(api, "ancestor").mockImplementation(ancestor);
    // The slice itself is not under test here; keep it from touching the
    // network so only the widening decides what happens.
    vi.spyOn(api, "slice").mockImplementation((_tree, options = {}) =>
      options.around !== undefined
        ? Promise.resolve(bare(options.root))
        : (new Promise(() => {}) as ReturnType<typeof api.slice>),
    );
    return mountPanel();
  }

  afterEach(() => vi.restoreAllMocks());

  it("roots at the widened ancestor and keeps the node drawn", async () => {
    const { result } = runJump(async () => ({
      node: 3266,
      leaves: 20,
      climbed: 12,
      reached_root: false,
    }));

    await actAsync(() => result.current[1].focusWithContext(leaf));

    expect(result.current[0].path).toEqual([3266]);
  });

  it("clears an earlier jump's message once a jump lands", async () => {
    // "211 is not in this tree" is about a question the next jump answers;
    // left up, it sits over a panel that has since moved.
    const { result } = runJump(async () => ({
      node: 3266, leaves: 20, climbed: 12, reached_root: false,
    }));
    await actAsync(() => result.current[1].reportJumpFailure("211 is not in vibrio-upgma.", true));
    expect(result.current[0].jumpError).not.toBeNull();
    expect(result.current[0].jumpErrorFades).toBe(true);

    await actAsync(() => result.current[1].focusWithContext(leaf));
    expect(result.current[0].jumpError).toBeNull();
  });

  it("does not let a failed request fade", async () => {
    const { result } = runJump(async () => {
      throw new ApiError(404, { detail: "Not Found", code: "not_found" });
    });
    await actAsync(() => result.current[1].reportJumpFailure("earlier answer", true));
    await actAsync(() => result.current[1].focusWithContext(leaf));
    expect(result.current[0].jumpError).toMatch(/could not work out where/i);
    expect(result.current[0].jumpErrorFades).toBe(false);
  });

  it("does not move the view when the widening fails", async () => {
    // What shipped: the failure silently fell back to focusing the bare node,
    // so when the running server predated /ancestor every jump 404'd and
    // rooted the panel at a single leaf — the exact symptom the endpoint was
    // added to remove, with nothing on screen to say a call had failed.
    const { result } = runJump(async () => {
      throw new ApiError(404, { code: "not_found", detail: "No such route" });
    });

    await actAsync(() => result.current[1].focusWithContext(leaf));

    expect(result.current[0].path).toEqual([]);
    // Reported separately from `error`, which describes the slice on screen:
    // this view is still perfectly valid, it is the move that did not happen.
    expect(result.current[0].jumpError).toMatch(/could not work out where/i);
    expect(result.current[0].error).toBeNull();
  });
});

describe("the mark a jump leaves", () => {
  const leaf = 3296;
  const ancestorAt = 3266;

  function mounted() {
    vi.spyOn(api, "ancestor").mockImplementation(async () => ({
      node: ancestorAt,
      leaves: 20,
      climbed: 12,
      reached_root: false,
    }));
    vi.spyOn(api, "slice").mockImplementation((_tree, options = {}) =>
      options.around !== undefined
        ? Promise.resolve(bare(options.root))
        : (new Promise(() => {}) as ReturnType<typeof api.slice>),
    );
    return mountPanel();
  }

  afterEach(() => vi.restoreAllMocks());

  it("survives going back, so the leaf stays drawn as the view widens", async () => {
    // Reported from use: the found leaf re-collapsed behind a wedge the moment
    // the view widened, so "where is this leaf in the whole tree" was the one
    // question the mark could not answer (§33). Going back is safe to carry it
    // through — the new root is an ancestor, so the node is still inside.
    const { result } = mounted();
    await actAsync(() => result.current[1].focusWithContext(leaf));
    expect(result.current[0].arrivedAt).toBe(leaf);

    await actAsync(() => result.current[1].back());

    expect(result.current[0].path).toEqual([]);
    expect(result.current[0].arrivedAt).toBe(leaf);
  });

  it("survives a reset to the whole tree", async () => {
    const { result } = mounted();
    await actAsync(() => result.current[1].focusWithContext(leaf));

    await actAsync(() => result.current[1].reset());

    expect(result.current[0].path).toEqual([]);
    expect(result.current[0].arrivedAt).toBe(leaf);
  });

  it("is dropped by clearMark, which is what the header's x calls", async () => {
    // The pin and the mark are one state, so clearing the mark must unpin:
    // otherwise the view holds a leaf out of a wedge for a mark that is no
    // longer on screen or in the header.
    const { result } = mounted();
    await actAsync(() => result.current[1].focusWithContext(leaf));

    await actAsync(() => result.current[1].clearMark());

    expect(result.current[0].arrivedAt).toBeNull();
  });

  it("survives focusing a clade, so expanding the wedge that holds it keeps it", async () => {
    // Reported from use: expanding the marked wedge dropped the pin, and the
    // highlight it left behind landed on an unrelated node (§37.10). Whether
    // the clade contains the leaf is the server's to say, not the client's.
    const { result } = mounted();
    await actAsync(() => result.current[1].focusWithContext(leaf));

    await actAsync(() => result.current[1].focus(9999));

    expect(result.current[0].arrivedAt).toBe(leaf);
    expect(result.current[0].path).toEqual([ancestorAt, 9999]);
  });

  it("is replaced by a new jump, not added to", async () => {
    const { result } = mounted();
    await actAsync(() => result.current[1].focusWithContext(leaf));
    await actAsync(() => result.current[1].focusWithContext(4000));
    expect(result.current[0].arrivedAt).toBe(4000);
  });
});

describe("navigating back to a view already seen", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    sliceCache.clear();
  });

  /** A slice whose root is whatever was asked for, so views are told apart. */
  function reply(root: number | undefined) {
    const nodes = 3;
    const range = Array.from({ length: nodes }, (_, k) => k);
    return {
      tree: "vibrio-upgma",
      root: root ?? 0,
      budget: 120,
      displayed_leaves: nodes,
      hidden_leaves: 0,
      total_leaves: nodes,
      nodes: {
        id: range.map((k) => (root ?? 0) * 100 + k),
        parent: range.map((k) => k - 1),
        label: range.map((k) => `leaf${k}`),
        branch_len: range.map(() => 0.1),
        true_leaf_count: range.map(() => 1),
        truncated: range.map(() => false),
      },
      comparison: null,
    };
  }

  function runPanel() {
    const slice = vi
      .spyOn(api, "slice")
      .mockImplementation(async (_tree, options = {}) => reply(options.root));
    return { slice, ...mountPanel() };
  }

  it("marks the wedge the server says stands in for an undrawable leaf", async () => {
    // The half the client cannot compute: a wedge's subtree is not in the
    // slice, so there is nothing here to test containment against. `keep` is
    // best-effort — widen far enough and the marked leaf goes behind a wedge —
    // and without this the header named a leaf with nothing on screen to point
    // at (§33).
    vi.spyOn(api, "ancestor").mockImplementation(async () => ({
      node: 2,
      leaves: 20,
      climbed: 3,
      reached_root: false,
    }));
    vi.spyOn(api, "slice").mockImplementation(async (_tree, options = {}) => ({
      ...reply(options.root),
      kept: { node: 7114, exact: false, label: "1203" },
    }));
    const { result } = mountPanel();

    await actAsync(() => result.current[1].focusWithContext(3296));

    // The leaf is still what was asked for, and what the chip names...
    expect(result.current[0].arrivedAt).toBe(3296);
    // ...but the thing to put the mark on is the wedge the server named.
    expect(result.current[0].markAt).toEqual({ node: 7114, exact: false, label: "1203" });
  });

  it("changes the mark only when the slice that answers it arrives", async () => {
    // §37.4: a second jump into a marked panel once set the new target at
    // once while the old slice was still on screen, and for a render the old
    // slice's mark answered the new question. A jump is one request now
    // (§40), so the target and its slice arrive together — this holds the
    // second jump's answer back and checks nothing moves before it lands.
    vi.spyOn(api, "ancestor").mockImplementation(async (_tree, node) => ({
      node: node + 1000,
      leaves: 20,
      climbed: 1,
      reached_root: false,
    }));
    let release: (() => void) | null = null;
    vi.spyOn(api, "slice").mockImplementation(async (_tree, options = {}) => {
      if (options.keep === 22) await new Promise<void>((done) => (release = done));
      return { ...reply(options.root), kept: { node: options.keep!, exact: true, label: `st${options.keep}` } };
    });
    const { result } = mountPanel();

    await actAsync(() => result.current[1].focusWithContext(11));
    expect(result.current[0].markAt).toEqual({ node: 11, exact: true, label: "st11" });

    await actAsync(() => result.current[1].focusWithContext(22));
    // Still the first jump, whole: its target, its slice, its mark.
    expect(result.current[0].arrivedAt).toBe(11);
    expect(result.current[0].markAt).toEqual({ node: 11, exact: true, label: "st11" });

    await actAsync(async () => release!());
    expect(result.current[0].arrivedAt).toBe(22);
    expect(result.current[0].markAt).toEqual({ node: 22, exact: true, label: "st22" });
  });

  it("says when the marked leaf is outside the view rather than marking anything", async () => {
    // Focusing a clade elsewhere keeps the pin (§37.10); the server answers a
    // `keep` outside the root with `kept: null`, and that must read as "not
    // in this view", not as "nothing is marked".
    vi.spyOn(api, "ancestor").mockImplementation(async () => ({
      node: 2, leaves: 20, climbed: 3, reached_root: false,
    }));
    vi.spyOn(api, "slice").mockImplementation(async (_tree, options = {}) => ({
      ...reply(options.root),
      // Root 2 holds the leaf; root 5 does not.
      kept: options.keep !== undefined && options.root === 2
        ? { node: options.keep, exact: true, label: "1203" }
        : null,
    }));
    const { result } = mountPanel();

    await actAsync(() => result.current[1].focusWithContext(3296));
    expect(result.current[0].markAt).toEqual({ node: 3296, exact: true, label: "1203" });
    expect(result.current[0].markOffView).toBe(false);

    await actAsync(() => result.current[1].focus(5));
    expect(result.current[0].arrivedAt).toBe(3296);
    expect(result.current[0].markAt).toBeNull();
    expect(result.current[0].markOffView).toBe(true);

    await actAsync(() => result.current[1].back());
    expect(result.current[0].markOffView).toBe(false);
    expect(result.current[0].markAt).toEqual({ node: 3296, exact: true, label: "1203" });
  });

  describe("removing the pin keeps the picture (§40)", () => {
    function pinned() {
      vi.spyOn(api, "ancestor").mockImplementation(async () => ({
        node: 2, leaves: 20, climbed: 3, reached_root: false,
      }));
      const slice = vi.spyOn(api, "slice").mockImplementation(async (_tree, options = {}) => ({
        ...reply(options.root),
        kept: options.keep !== undefined ? { node: options.keep, exact: true, label: "1203" } : null,
      }));
      return { slice, ...mountPanel() };
    }

    it("asks for nothing when the pinned view is the one on screen", async () => {
      // Measured: 37 of 213 slice requests in a navigation walk only replaced
      // a pinned picture with a near-identical unpinned one.
      const { slice, result } = pinned();
      await actAsync(() => result.current[1].focusWithContext(3296));
      const shown = result.current[0].slice;
      const asked = slice.mock.calls.length;

      await actAsync(() => result.current[1].clearMark());

      expect(slice.mock.calls.length).toBe(asked);
      expect(result.current[0].slice).toBe(shown);
      expect(result.current[0].arrivedAt).toBeNull();
      expect(result.current[0].markAt).toBeNull();
    });

    it("still shows a picture when the pinned view had not arrived yet", async () => {
      // Back after a jump asks for the wider view pinned; clear the mark
      // while that is in flight and the request is aborted — skipping the
      // unpinned one would leave the panel waiting on nothing.
      vi.spyOn(api, "ancestor").mockImplementation(async () => ({
        node: 2, leaves: 20, climbed: 3, reached_root: false,
      }));
      vi.spyOn(api, "slice").mockImplementation((_tree, options = {}) =>
        options.keep !== undefined && options.root === undefined
          ? (new Promise(() => {}) as ReturnType<typeof api.slice>)
          : Promise.resolve({
              ...reply(options.root),
              kept: options.keep !== undefined ? { node: options.keep, exact: true, label: "1203" } : null,
            }),
      );
      const { result } = mountPanel();
      await actAsync(() => result.current[1].focusWithContext(3296));
      await actAsync(() => result.current[1].back());
      expect(result.current[0].loading).toBe(true);

      await actAsync(() => result.current[1].clearMark());

      expect(result.current[0].loading).toBe(false);
      expect(result.current[0].slice?.root).toBe(0);
      expect(result.current[0].arrivedAt).toBeNull();
    });

    it("lands a jump in one request: the panel finds the answer in the cache", async () => {
      // §40: `/ancestor` then the slice was two round trips per jump.
      const { slice, result } = pinned();
      await actAsync(async () => {});
      const before = slice.mock.calls.length;

      await actAsync(() => result.current[1].focusWithContext(3296));

      const made = slice.mock.calls.slice(before).map(([, options]) => options ?? {});
      expect(made.filter((o) => o.around !== undefined)).toHaveLength(1);
      // The panel did not ask for the view it landed on: the jump's answer
      // was already in the cache.
      expect(made.filter((o) => o.around === undefined && o.root === 2)).toHaveLength(0);
      expect(result.current[0].path).toEqual([2]);
      expect(result.current[0].markAt).toEqual({ node: 3296, exact: true, label: "1203" });
    });


    it("goes unpinned from the next navigation on", async () => {
      const { slice, result } = pinned();
      await actAsync(() => result.current[1].focusWithContext(3296));
      await actAsync(() => result.current[1].clearMark());
      const before = slice.mock.calls.length;

      await actAsync(() => result.current[1].focus(7));
      await actAsync(() => result.current[1].back());

      const after = slice.mock.calls.slice(before);
      expect(after.length).toBeGreaterThan(0);
      expect(after.every(([, options]) => options?.keep === undefined)).toBe(true);
      expect(result.current[0].markAt).toBeNull();
    });
  });

  it("has nothing to mark until a jump asks for one", async () => {
    const { result } = runPanel();
    await actAsync(async () => {});
    expect(result.current[0].markAt).toBeNull();
  });

  it("serves a slice it already holds instead of asking again", async () => {
    // The gap this closes: pressing Back onto a view that had just been on
    // screen went to the network for bytes the browser already had. It was
    // never slow — ~2.9 ms — but it is the one operation where holding the
    // whole tree in memory is a genuine advantage, and conceding it bought
    // nothing.
    const { slice, result } = runPanel();
    await actAsync(() => {});
    const afterFirst = slice.mock.calls.length;

    await actAsync(() => result.current[1].focus(42));
    expect(slice.mock.calls.length).toBeGreaterThan(afterFirst);

    const afterFocus = slice.mock.calls.length;
    await actAsync(() => result.current[1].back());

    expect(slice.mock.calls.length).toBe(afterFocus);
    expect(result.current[0].path).toEqual([]);
    expect(result.current[0].tree).not.toBeNull();
  });

  it("does not flash a spinner over a picture it already has", async () => {
    // A cache hit is applied synchronously, so `loading` never goes true at
    // all. Asserting only on the final value would prove nothing — it is false
    // once any fetch settles too — so this records every render.
    vi.spyOn(api, "slice").mockImplementation(async (_tree, options = {}) =>
      reply(options.root),
    );
    const seen: boolean[] = [];
    const { result } = renderHook(() => {
      const side = useSide("vibrio-upgma", "a__b");
      seen.push(side[0].loading);
      return side;
    });

    await actAsync(() => {});
    await actAsync(() => result.current[1].focus(42));
    seen.length = 0;
    await actAsync(() => result.current[1].back());

    expect(seen).not.toContain(true);
    expect(result.current[0].tree).not.toBeNull();
  });

  it("reload asks the server again rather than re-serving what it holds", async () => {
    // A tree id outlives the bytes behind it, so a cache that survived reload
    // would make the button visibly do nothing — worse than not having one.
    const { slice, result } = runPanel();
    await actAsync(() => {});
    // Go away and come back, so the root view is definitely held and served
    // from the cache — otherwise this passes whether reload discards anything
    // or not.
    await actAsync(() => result.current[1].focus(42));
    await actAsync(() => result.current[1].back());
    const before = slice.mock.calls.length;

    await actAsync(() => result.current[1].reload());

    expect(slice.mock.calls.length).toBeGreaterThan(before);
  });
});
