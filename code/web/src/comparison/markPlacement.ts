/**
 * What to do with a panel's mark when the view re-renders (§37.7, §37.9).
 *
 * Pulled out of the view's effect so it can be tested: the effect runs for
 * *both* panels whenever *either* panel's slice changes, and a decision taken
 * per panel without looking at which one changed is what stopped a search's
 * flash in the panel that arrived first.
 */

/** An arrival a panel has marked: which node, what the chip calls it, against which slice. */
export interface Placed {
  arrival: number;
  label: string;
  /** False once a jump into the other panel has taken the mark. */
  shown: boolean;
  /** The slice the mark was last placed on — compared by identity. */
  slice: unknown;
}

/**
 * - `flash`: a new arrival. Mark it and blink, so the eye finds it.
 * - `move`: the same arrival, drawn anew by a new slice of *this* panel (back,
 *   a resize). Re-place it steadily: blinking again would announce an arrival
 *   that did not happen.
 * - `keep`: nothing about this panel changed. Touching it anyway — even a
 *   steady re-place — stops a blink still running from its own arrival, which
 *   is how a search that found a name in both trees ended up flashing in only
 *   the panel whose slice came back last.
 */
export function markAction(
  prior: Placed | null,
  arrival: number,
  slice: unknown,
): "flash" | "move" | "keep" {
  if (!prior || prior.arrival !== arrival) return "flash";
  // A jump into the other panel took the mark: this one still holds the pin,
  // but showing it again would put two marks on screen.
  if (!prior.shown) return "keep";
  return prior.slice === slice ? "keep" : "move";
}
