/**
 * "Order to match the other tree" (§55.3), as two sibling orders.
 *
 * Phylo.io's "Equalize trees → Reorder" rotates one tree's siblings so that the
 * clades both trees share come out in the same top-to-bottom order. Here that
 * is a {@link ChildOrder} per panel, applied by the viewer, and nothing else: the
 * clades, their values and their ids are untouched, so no slice is fetched and
 * the slice cache key does not change.
 *
 * **The left panel is the reference and is drawn in its stored pre-order** —
 * the order of its own Newick file. The right panel puts each node's children
 * in the pre-order of their counterparts in the left tree (`corresponds`).
 * Pre-order is the one order the right panel can know for nodes the left
 * panel does not show: a counterpart folded inside a wedge on the left still
 * has a stored id. Ordering the left panel by name, as it is by default, would
 * need the left panel's drawn rank of every counterpart, which it has only for
 * what it draws. Two siblings whose counterparts are in disjoint clades come
 * out in the order those clades are drawn on the left; a child with no
 * counterpart goes after the matched ones and keeps its usual order.
 */

import { orderByKey, orderByName, type ChildOrder, type NewickNode } from "phylo-tree-viewer";

/** The stored id a slice node carries (`treeFromSlice` puts it in metadata). */
export function storedIdOf(node: NewickNode): number | undefined {
  const id = (node.metadata as { storedId?: unknown } | undefined)?.storedId;
  return typeof id === "number" ? id : undefined;
}

/**
 * The two panels' sibling orders.
 *
 * `counterpartOnLeft` maps a right-tree stored id to its counterpart's stored
 * id in the left tree, or undefined where there is none.
 */
export function siblingOrders(
  matchOrder: boolean,
  counterpartOnLeft: (rightStoredId: number) => number | undefined,
): [ChildOrder, ChildOrder] {
  if (!matchOrder) return [orderByName, orderByName];
  return [
    orderByKey(storedIdOf),
    orderByKey((node) => {
      const id = storedIdOf(node);
      return id === undefined ? undefined : counterpartOnLeft(id);
    }),
  ];
}
