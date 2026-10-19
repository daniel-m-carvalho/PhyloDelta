/**
 * What you are looking at, in the URL.
 *
 * Without this, refreshing returns you to the chooser — which is wrong twice
 * over: a comparison of two large trees is expensive to get back to, and a URL
 * that does not name what it shows cannot be sent to anyone.
 *
 * The hash rather than the path, so no server rewrite rule is needed: the app
 * is served as static files behind nginx in the container, and a path-based
 * route would 404 on reload unless nginx were taught about it.
 */

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Everything the View menu and the typing footer decide.
 *
 * In the URL with the rest of the view, not in localStorage: these change what
 * the picture *means* — which colour is divergence, what the bars count — so a
 * link that carried the navigation but not the options would show the
 * recipient a different figure from the one being described. It also makes
 * refresh lossless, which is how the gap was noticed.
 */
export interface ViewOptions {
  gradient: boolean;
  /**
   * Paint leaves by the moved-leaves metric instead of the gradient (§46).
   * One presentation at a time: setting it clears `gradient`, and the reverse.
   */
  moved: boolean;
  /** Where the gradient is drawn. */
  colorTarget: "branches" | "clades";
  typing: boolean;
  /** Typing columns composed into each leaf's bar. */
  columns: string[];
  barScale: "log" | "linear";
  /** Label every collapsed clade with its leaf count. */
  cladeSizes: boolean;
  /**
   * Cladogram: branch position by depth, so the eye reads topology. Phylogram:
   * by branch length, so it reads distance. In the URL because the same tree
   * drawn either way says different things.
   */
  layout: "cladogram" | "phylogram";
  /** Write each branch's length beside it, where it fits (§44). */
  lengths: boolean;
  /** How a phylogram draws lengths: to scale, or as log(1 + length) (§44). */
  lengthScale: "linear" | "log";
  /**
   * Colours the user chose for particular typing categories, by category key
   * (§43). In the URL so a refresh, a shared link and the exported report all
   * show the colours that were chosen rather than the palette's.
   */
  colors: Record<string, string>;
}

export const DEFAULT_OPTIONS: ViewOptions = {
  gradient: true,
  moved: false,
  colorTarget: "branches",
  typing: false,
  columns: [],
  barScale: "log",
  cladeSizes: false,
  layout: "cladogram",
  lengths: false,
  lengthScale: "linear",
  colors: {},
};

export interface ViewState {
  /** The comparison being shown, or null for the chooser. */
  comparison: string | null;
  /** Root ids each side has navigated into, oldest first. */
  left: number[];
  right: number[];
  options: ViewOptions;
}

const EMPTY: ViewState = { comparison: null, left: [], right: [], options: DEFAULT_OPTIONS };

/**
 * `cc=e03131.Human`: the colour first, because it has a fixed shape and a
 * category name is arbitrary text that may itself contain a dot. An entry that
 * is not six hex digits and a name is dropped — a hand-edited link should not
 * paint a category with a colour the browser cannot read.
 */
function parseColors(entries: string[]): Record<string, string> {
  const colors: Record<string, string> = {};
  for (const entry of entries) {
    const match = /^([0-9a-f]{6})\.(.+)$/i.exec(entry);
    if (match) colors[match[2]] = `#${match[1].toLowerCase()}`;
  }
  return colors;
}

function parse(hash: string): ViewState {
  // #/c/<id>?l=3,900&r=12
  const match = /^#\/c\/([^?]+)(?:\?(.*))?$/.exec(hash);
  if (!match) return EMPTY;
  const query = new URLSearchParams(match[2] ?? "");
  const ids = (value: string | null): number[] =>
    (value ?? "")
      .split(",")
      .map((part) => Number.parseInt(part, 10))
      .filter((n) => Number.isFinite(n));
  return {
    comparison: decodeURIComponent(match[1]),
    left: ids(query.get("l")),
    right: ids(query.get("r")),
    options: {
      // Absent means the default, so only what differs is ever written and an
      // old link without these keys still opens the view it always did.
      gradient: query.get("g") !== "0" && query.get("mv") !== "1",
      moved: query.get("mv") === "1",
      colorTarget: query.get("gc") === "clades" ? "clades" : "branches",
      typing: query.get("t") === "1",
      // Repeated keys rather than a joined string: a column name is arbitrary
      // text and may itself contain a separator.
      columns: query.getAll("col"),
      barScale: query.get("bs") === "linear" ? "linear" : "log",
      cladeSizes: query.get("cs") === "1",
      layout: query.get("lm") === "phylogram" ? "phylogram" : "cladogram",
      lengths: query.get("bl") === "1",
      lengthScale: query.get("ls") === "log" ? "log" : "linear",
      colors: parseColors(query.getAll("cc")),
    },
  };
}

function format(state: ViewState): string {
  if (!state.comparison) return "";
  const query = new URLSearchParams();
  if (state.left.length) query.set("l", state.left.join(","));
  if (state.right.length) query.set("r", state.right.join(","));
  const options = state.options ?? DEFAULT_OPTIONS;
  if (options.moved) query.set("mv", "1");
  else if (!options.gradient) query.set("g", "0");
  if (options.colorTarget !== DEFAULT_OPTIONS.colorTarget) query.set("gc", options.colorTarget);
  if (options.typing) query.set("t", "1");
  for (const column of options.columns) query.append("col", column);
  if (options.barScale !== DEFAULT_OPTIONS.barScale) query.set("bs", options.barScale);
  if (options.cladeSizes) query.set("cs", "1");
  if (options.layout !== DEFAULT_OPTIONS.layout) query.set("lm", options.layout);
  if (options.lengths) query.set("bl", "1");
  if (options.lengthScale !== DEFAULT_OPTIONS.lengthScale) query.set("ls", options.lengthScale);
  // Sorted, so the same choices always write the same link.
  for (const [category, color] of Object.entries(options.colors ?? {}).sort(([a], [b]) => a.localeCompare(b))) {
    query.append("cc", `${color.replace(/^#/, "")}.${category}`);
  }
  const tail = query.toString();
  return `#/c/${encodeURIComponent(state.comparison)}${tail ? `?${tail}` : ""}`;
}

/**
 * A write may leave the options out, and then they are kept.
 *
 * Navigation and presentation change independently — focusing a subtree must
 * not silently reset the colouring — so a caller states only what it is
 * changing.
 */
export type ViewStateWrite = Omit<ViewState, "options"> & { options?: ViewOptions };

export function useUrlState(): [ViewState, (next: ViewStateWrite) => void] {
  const [state, setState] = useState<ViewState>(() => parse(window.location.hash));

  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    // Back and forward should move between views, not out of the app.
    const onHash = () => setState(parse(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const write = useCallback((next: ViewStateWrite) => {
    const merged: ViewState = { ...next, options: next.options ?? stateRef.current.options };
    const hash = format(merged);
    if (hash === window.location.hash) return;
    // replaceState, not a hash assignment: navigating within a comparison
    // should not fill the history with one entry per expansion, or Back would
    // mean "undo one expand" rather than "leave this comparison".
    window.history.replaceState(null, "", hash || window.location.pathname);
    setState(merged);
  }, []);

  return [state, write];
}
