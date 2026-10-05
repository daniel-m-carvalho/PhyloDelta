/**
 * One side of a comparison, and how it navigates.
 *
 * **The server summarises; the client navigates by re-rooting.** A slice is a
 * subtree reduced to a leaf budget, so going deeper is not "reveal what is
 * already loaded" — it is another request, rooted at the node the user chose.
 * That is the whole point: a 500k-leaf tree is never in the browser, only ever
 * a few hundred nodes standing in for it.
 *
 * Navigation is therefore a **stack of root ids**. Focusing pushes, going back
 * pops, resetting clears. `budget` is the second dimension: raising it shows
 * more of the current subtree without moving, which is what "expand all" means
 * on a tree small enough to afford it.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import { sliceCache, type SliceKeyParts } from "../api/sliceCache";
import type { TreeSlice } from "../api/types";
import { gradientFrom, type Gradient } from "../tree/comparisonValues";
import { treeFromSlice, type SliceTree } from "../tree/fromSlice";

/**
 * Roughly how many vertical pixels one displayed tip needs to be legible.
 *
 * A slice's tips are mostly **wedges**, not leaves — at this budget the vibrio
 * pair shows 19 real leaves and 31 collapsed clades — so this is really the
 * row spacing of the view, and the wedge height is derived from it
 * (`ComparisonView`). Fourteen leaves room for a triangle that can be told
 * apart from its neighbours and still aimed at with a mouse.
 *
 * Six is where the staircase of a ladder-shaped tree stays visible as
 * separate steps. Below about three, adjacent leaves merge: the terminals —
 * which the cladogram pins to a single column — fuse into a solid bar, and
 * the structure between them turns into a block of colour. That is what a
 * fixed budget of 400 produced in a 700px panel (1.7px per leaf), and it is
 * why the trees looked like a smear rather than a tree.
 */
export const PIXELS_PER_LEAF = 14;

/** Used before a panel has been measured, and as the floor for a tiny window. */
export const DEFAULT_BUDGET = 120;

/** Budgets are rounded to this, so small resizes do not each cost a request. */
const BUDGET_STEP = 25;

/**
 * How many leaves this panel can actually draw.
 *
 * Asking the server for more detail than the client can render is the failure
 * this project is about, in miniature: the request succeeds, the bytes
 * arrive, and the picture is worse. The budget is a property of the viewport,
 * not a constant.
 */
export function readableBudget(panelHeightPx: number): number {
  // Zero means "not measured yet", and the caller waits rather than guessing:
  // fetching at a placeholder budget and again at the real one is two slices
  // per panel on every load, for a picture nobody sees.
  if (!panelHeightPx) return 0;
  const fits = Math.max(40, Math.min(600, Math.floor(panelHeightPx / PIXELS_PER_LEAF)));
  // Quantised, so the few pixels a layout shifts by while settling — or a
  // window nudged by a scrollbar — do not each cost a slice. Observed: the
  // panel measured 600px then 577px on load, and the difference between 100
  // leaves and 96 is invisible, but it was a second request for both trees.
  return Math.round(fits / BUDGET_STEP) * BUDGET_STEP;
}

/**
 * Above this, "expand all" is not offered.
 *
 * Not a guess about the server — it answers fine — but about the browser,
 * which is the thing this project is measuring. Asking for every leaf of a
 * 500k-leaf tree would reproduce exactly the failure this design exists to
 * avoid.
 */
export const EXPAND_ALL_LIMIT = 5_000;

/**
 * How much of the other tree a cross-tree jump should land in.
 *
 * Not a display preference — it is what stops a jump resolving to a tip. A
 * leaf's match is exact and therefore itself a leaf, and a panel rooted at a
 * leaf is one dot. Twenty is enough to show a neighbourhood and small enough
 * to stay inside a normal panel's budget, so every tip is drawn and the leaf
 * that was asked about is visible rather than summarised behind a wedge.
 */
export const JUMP_CONTEXT_LEAVES = 20;

export interface SideState {
  treeId: string;
  slice: TreeSlice | null;
  tree: SliceTree | null;
  gradient: Gradient;
  budget: number;
  /** What the viewport allows; `budget` differs once the user overrides it. */
  autoBudget: number;
  loading: boolean;
  error: string | null;
  /** Root ids visited, oldest first. The last entry is where we are. */
  path: number[];
  canGoBack: boolean;
  /**
   * The node this panel was sent to from the other one, if that is what put it
   * here. Null after any ordinary navigation.
   *
   * Exposed so the view can point at it. Landing in the right neighbourhood is
   * only half of "find this leaf in the other tree" — among eighty tips, one
   * of which is the answer, the panel still has to say which.
   */
  arrivedAt: number | null;
  /**
   * The node to actually mark for {@link arrivedAt}, which is not always it.
   *
   * `keep` is best-effort (§33): widen far enough — back out to the whole tree
   * at the viewport's own budget — and the marked leaf goes behind a wedge.
   * The slice reports which wedge, because nothing here could work it out: a
   * wedge's subtree is not in the response. `exact` is false in that case, and
   * the view says the mark is standing in rather than quietly moving it.
   *
   * Null when nothing is marked, or when the pin did not apply at all.
   */
  markAt: { node: number; exact: boolean } | null;
  /**
   * Why a jump into this panel could not be made, if one could not.
   *
   * Separate from `error`, which is about the slice on screen: this is about a
   * move that never happened, so the view is still valid and only the request
   * failed.
   */
  jumpError: string | null;
}

export interface SideActions {
  focus: (storedId: number) => void;
  /**
   * Focus a node arriving from the *other* panel, widened to something
   * readable first.
   *
   * A cross-tree match is a node id and nothing else — this panel's slice does
   * not contain it, so its size and its ancestors are unknown here. Leaf
   * matches are exact and therefore always tips, so focusing one directly drew
   * a panel containing a single dot. The server resolves the ancestor; falling
   * back to the bare node if that call fails is still better than not moving.
   */
  focusWithContext: (storedId: number) => void;
  /** Report that a jump into this panel is impossible, for the view to show. */
  reportJumpFailure: (reason: string) => void;
  dismissJumpFailure: () => void;
  back: () => void;
  reset: () => void;
  /** Drop the mark a jump left, and with it the guarantee that it stays drawn. */
  clearMark: () => void;
  setBudget: (budget: number) => void;
  expandAll: () => void;
  collapseAll: () => void;
  reload: () => void;
}

const NO_GRADIENT: Gradient = {
  similarityOf: () => undefined,
  correspondingTo: () => undefined,
};

export function useSide(
  treeId: string,
  compare: string | undefined,
  metric = "rf",
  initialPath: number[] = [],
  autoBudget: number = DEFAULT_BUDGET,
  labelClades: boolean = false,
): [SideState, SideActions] {
  const [path, setPath] = useState<number[]>(initialPath);

  // Follow the URL when it changes underneath us — a Back press, or a link
  // pasted into the bar. Guarded by a content comparison, because the URL is
  // also written *from* this state: without that, every navigation would
  // round-trip through the address bar and set the state it came from.
  const wanted = initialPath.join(",");
  useEffect(() => {
    setPath((current) => (current.join(",") === wanted ? current : wanted ? wanted.split(",").map(Number) : []));
  }, [wanted]);
  const [budget, setBudget] = useState(autoBudget);
  /*
   * A node this panel was sent to from the other one, which must stay drawn
   * rather than be folded into a wedge.
   *
   * Held alongside the path rather than inside it because it is not a
   * navigation step: the panel is rooted at an ancestor, and this only says
   * which node inside it was actually asked for.
   *
   * **This is the mark, so it lives as long as the mark does** (§33): set by a
   * jump, moved by the next one, and otherwise removed only when the user asks
   * — the header's `×` or Escape, through {@link SideActions.clearMark}.
   *
   * It used to be cleared by *any* navigation, going back included, which is
   * what a supervisor reported: the found leaf re-collapsed behind a wedge the
   * moment you widened the view, so the one question a mark exists to answer —
   * where is this leaf in the whole tree — was the question it could not
   * survive. Going back is safe to carry it through because the new root is
   * always an **ancestor** of the old one, so the kept node is still inside the
   * view; only {@link SideActions.focus} into a different clade can move
   * somewhere the node is not, and that is the one case that still clears it.
   */
  const [keep, setKeep] = useState<number | null>(null);
  const [jumpError, setJumpError] = useState<string | null>(null);
  // Follows the viewport until the user overrides it with expand/collapse all.
  const [overridden, setOverridden] = useState(false);

  useEffect(() => {
    if (!overridden) setBudget(autoBudget);
  }, [autoBudget, overridden]);
  const [slice, setSlice] = useState<TreeSlice | null>(null);
  /**
   * The `keep` the slice on screen was asked with — which is not always the
   * current one. A jump sets `keep` at once and the slice that honours it
   * arrives later, so in between `slice.kept` answers the *previous* jump.
   * Read on its own, that paired a new target with the old mark (§37).
   */
  const [shownKeep, setShownKeep] = useState<number | null>(null);
  const [tree, setTree] = useState<SliceTree | null>(null);
  const [gradient, setGradient] = useState<Gradient>(NO_GRADIENT);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  // The root currently displayed; undefined means "the tree's own root",
  // which is what the API assumes when `root` is omitted.
  const root = path.length ? path[path.length - 1] : undefined;
  const latest = useRef(0);

  // The slice this panel currently draws, so the cache can be told when the
  // panel moves off it and it becomes an eviction candidate again.
  const rendered = useRef<SliceKeyParts | null>(null);

  useEffect(() => {
    // Nothing to ask for until the panel has been measured.
    if (budget <= 0) return;

    const parts: SliceKeyParts = { treeId, root, budget, compare, metric, keep: keep ?? undefined };

    /**
     * Put a slice on screen, from wherever it came.
     *
     * The tree is rebuilt here rather than cached alongside the slice, because
     * `labelClades` changes the names the viewer shows without changing the
     * response — so the built tree is a function of two things and only one of
     * them is the request.
     */
    const show = (fetched: TreeSlice) => {
      const built = treeFromSlice(fetched, { labelClades });
      setSlice(fetched);
      setShownKeep(parts.keep ?? null);
      setTree(built);
      setGradient(gradientFrom(built, fetched.comparison));
      setLoading(false);
      // Protect what is visible, release what no longer is. At most two
      // entries are ever protected, one per panel, which is what keeps the
      // rendered tier from crowding out the eviction candidates.
      if (rendered.current) sliceCache.unrender(rendered.current);
      rendered.current = parts;
      sliceCache.render(parts);
    };

    // Navigation is faster than the network, so a slow earlier request must
    // not overwrite a newer one. Both guards matter: abort stops the work,
    // the sequence number stops a response that already escaped.
    const controller = new AbortController();
    const ticket = ++latest.current;

    // A slice already held is applied synchronously: no request, and no
    // `loading` at all, so going back to a view does not flash a spinner over
    // a picture the browser already has. The ticket is still taken, so an
    // older fetch still in flight cannot land on top of it.
    const held = sliceCache.get(parts);
    if (held) {
      setError(null);
      show(held);
      return () => controller.abort();
    }

    setLoading(true);
    setError(null);

    // Deliberately *not* routed through the cache's `registerPending`. It
    // exists to stop two callers fetching the same key twice, and this hook
    // already solves that more precisely with the abort and the ticket above.
    // Sharing one promise between panels would mean either panel's abort
    // rejecting the other's request — trading a duplicate fetch, which costs
    // ~6 KB, for a cross-panel failure.
    api
      .slice(treeId, {
        root,
        budget,
        compare,
        metric,
        keep: keep ?? undefined,
        signal: controller.signal,
      })
      .then((fetched) => {
        // Cached even when this response is stale for *this* panel: the
        // navigation it answers may well be visited again, and the bytes have
        // already been paid for.
        sliceCache.put(parts, fetched);
        if (ticket !== latest.current) return;
        show(fetched);
      })
      .catch((failed: unknown) => {
        if (ticket !== latest.current || controller.signal.aborted) return;
        setError(
          failed instanceof ApiError
            ? `${failed.message}${failed.hint ? ` — ${failed.hint}` : ""}`
            : String(failed),
        );
        setLoading(false);
      });

    return () => controller.abort();
    // `labelClades` only changes a node's display name, so the slice itself is
    // unchanged — but the tree handed to the viewer must be rebuilt for the
    // new names to reach it.
  }, [treeId, root, budget, compare, metric, nonce, labelClades, keep]);

  // A panel that goes away stops protecting its slice. Without this the entry
  // would sit in the rendered tier forever, evictable only as a last resort —
  // switching comparison after comparison would fill the budget with views no
  // panel is showing.
  useEffect(
    () => () => {
      if (rendered.current) sliceCache.unrender(rendered.current);
      rendered.current = null;
    },
    [],
  );

  const focus = useCallback(
    (storedId: number, keepVisible: number | null = null) => {
      setPath((current) =>
        current[current.length - 1] === storedId ? current : [...current, storedId],
      );
      setOverridden(false);
      setBudget(autoBudget);
      setKeep(keepVisible);
    },
    [autoBudget],
  );

  const actions: SideActions = {
    focus,

    focusWithContext: useCallback(
      (storedId: number) => {
        void api
          // No ceiling on how wide this may go. Capping it at the panel's
          // budget looked right — a subtree that fits draws every tip — but on
          // a ladder there is nothing between two leaves and thousands, so a
          // quarter of jumps stopped under the floor and landed on two dots.
          // `keep` below is what guarantees the leaf is drawn, at any size.
          .ancestor(treeId, storedId, { minLeaves: JUMP_CONTEXT_LEAVES })
          // The node asked about is kept drawn inside whatever it widened to,
          // however wide that is — see JUMP_CONTEXT_LEAVES and the slice's
          // `keep`.
          .then((context) => focus(context.node, storedId))
          .catch((failed) => {
            // Emphatically NOT a silent fall back to the bare node. That is
            // what this did first, and when the running server turned out to
            // predate the endpoint, every jump 404'd and quietly rooted the
            // panel at a single leaf — the exact symptom the endpoint was
            // added to remove, with nothing on screen to say a call had
            // failed. A wrong view that looks deliberate is worse than an
            // error, so the view does not move and the panel says why.
            setJumpError(
              `Could not work out where that leaf sits in ${treeId}. ` +
                (failed instanceof ApiError ? failed.message : String(failed)),
            );
          });
      },
      [treeId, focus],
    ),

    reportJumpFailure: useCallback((reason: string) => setJumpError(reason), []),

    dismissJumpFailure: useCallback(() => setJumpError(null), []),

    // Both of these widen the view, so the marked node stays inside it and
    // stays pinned: see `keep`. Neither clears the mark — that is `clearMark`.
    back: useCallback(() => {
      setPath((current) => current.slice(0, -1));
    }, []),

    reset: useCallback(() => {
      setPath([]);
      setOverridden(false);
      setBudget(autoBudget);
    }, [autoBudget]),

    clearMark: useCallback(() => setKeep(null), []),

    setBudget,

    // "Expand all" is a budget large enough to hold every leaf under the
    // current root — the server then has nothing left to summarise.
    expandAll: useCallback(() => {
      setOverridden(true);
      setBudget(Math.max(autoBudget, (slice?.total_leaves ?? 0) + 1));
    }, [slice, autoBudget]),

    collapseAll: useCallback(() => {
      setOverridden(true);
      setBudget(2);
    }, []),

    /**
     * Ask again, and mean it.
     *
     * Bumping the nonce alone would now re-run the effect straight into a cache
     * hit and change nothing on screen — a reload button that visibly does
     * nothing, which is worse than not having one. A tree id outlives the bytes
     * behind it (a rebuilt store keeps the id), so reload discards what is held
     * for this tree first.
     */
    reload: useCallback(() => {
      sliceCache.invalidateTree(treeId);
      setNonce((n) => n + 1);
    }, [treeId]),
  };

  return [
    {
      treeId,
      slice,
      tree,
      gradient,
      budget,
      autoBudget,
      loading,
      error,
      path,
      arrivedAt: keep,
      // From the slice, not inferred: only the server knows which wedge holds
      // a node it had to summarise. And only from a slice asked about *this*
      // node: until it arrives there is nothing to mark yet.
      markAt: keep === null || shownKeep !== keep ? null : (slice?.kept ?? null),
      jumpError,
      canGoBack: path.length > 0,
    },
    actions,
  ];
}
