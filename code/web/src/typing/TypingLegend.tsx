/**
 * What the bar colours mean, which typing columns they come from, and how bar
 * length is scaled.
 *
 * One legend for both panels, not one each: the colour scale is shared, so two
 * would be the same list twice — the library's own demo learned that, with
 * duplicate ramps floating over the leaf labels.
 *
 * Categories are read from the scale itself rather than from the data, because
 * the scale is what assigns the colours; deriving them separately is how a
 * legend comes to disagree with the picture it explains.
 */

import { useEffect, useRef } from "react";
import type { BarScale } from "phylo-tree-viewer";
import { CheckboxMenu } from "../ui/CheckboxMenu";

export function TypingLegend({
  assignments,
  segmentKeys,
  keys,
  onSegmentKeys,
  scale,
  onScale,
  loading,
  error,
  chosen = {},
  onColor,
  onResetColors,
}: {
  assignments: ReadonlyMap<string, string>;
  segmentKeys: string[];
  keys: string[];
  onSegmentKeys: (keys: string[]) => void;
  scale: BarScale;
  onScale: (scale: BarScale) => void;
  loading: boolean;
  error: string | null;
  /** Categories given a colour by the user (§43), by key. */
  chosen?: Record<string, string>;
  /** A colour chosen for one category. Absent: the swatches are not clickable. */
  onColor?: (category: string, color: string) => void;
  onResetColors?: () => void;
}) {
  const entries = [...assignments.entries()].sort(([a], [b]) =>
    String(a ?? "").localeCompare(String(b ?? "")),
  );

  const toggle = (key: string) =>
    onSegmentKeys(
      segmentKeys.includes(key)
        ? segmentKeys.filter((candidate) => candidate !== key)
        : [...segmentKeys, key],
    );

  return (
    <footer className="typing-legend">
      <div className="legend-head">
        <CheckboxMenu
          title="Colour by"
          summary={
            segmentKeys.length === 0
              ? "none"
              : segmentKeys.length <= 2
                ? segmentKeys.join(", ")
                : `${segmentKeys.length} columns`
          }
          items={keys.map((key) => ({
            key,
            label: key,
            checked: segmentKeys.includes(key),
          }))}
          onToggle={toggle}
          openUpward
        />


        <label className="legend-scale">
          Bar length
          <select value={scale} onChange={(event) => onScale(event.target.value as BarScale)}>
            <option value="linear">Linear</option>
            {/* Counts span orders of magnitude — most leaves have a handful of
                isolates and a few have hundreds — so on a linear scale almost
                every bar is a stub. */}
            <option value="log">Logarithmic</option>
          </select>
        </label>

        {onResetColors && Object.keys(chosen).length > 0 ? (
          <button type="button" className="legend-reset" onClick={onResetColors}>
            Reset colours
          </button>
        ) : null}

        {loading ? <span className="legend-note">loading…</span> : null}
        {error ? <span className="legend-note error">{error}</span> : null}
      </div>

      {!loading && !error && entries.length === 0 ? (
        <p className="legend-note">
          {segmentKeys.length === 0
            ? "Choose a column to colour by."
            : "No typing data for the leaves on screen."}
        </p>
      ) : null}

      <ul className="legend-swatches">
        {entries.map(([value, color]) => (
          <li key={value}>
            {onColor ? (
              <ColorSwatch category={value} color={color} chosen={value in chosen} onColor={onColor} />
            ) : (
              <span className="swatch" style={{ background: color }} aria-hidden="true" />
            )}
            {value}
          </li>
        ))}
      </ul>
    </footer>
  );
}

/**
 * A legend swatch that opens the browser's colour picker for its category.
 *
 * Applied on the picker's native `change` — when a colour is committed — and
 * not on `input`, which fires on every step of a drag: each one would redraw
 * both panels' bars and rewrite the URL, dozens of times a second. React's
 * `onChange` on a colour input is the `input` event, hence the listener.
 */
function ColorSwatch({
  category,
  color,
  chosen,
  onColor,
}: {
  category: string;
  color: string;
  chosen: boolean;
  onColor: (category: string, color: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const latest = useRef(onColor);
  latest.current = onColor;

  useEffect(() => {
    const element = input.current;
    if (!element) return;
    const commit = () => latest.current(category, element.value);
    element.addEventListener("change", commit);
    return () => element.removeEventListener("change", commit);
    // `color` too: a new colour remounts the input (its `key`), and the
    // listener has to follow it to the new element.
  }, [category, color]);

  return (
    <label
      className={chosen ? "swatch swatch-pick chosen" : "swatch swatch-pick"}
      style={{ background: color }}
      title={`Choose a colour for ${category}`}
    >
      <input
        ref={input}
        type="color"
        // Uncontrolled: the picker owns its value while open; a new colour
        // from outside (a reset, a shared link) remounts it via `key`.
        key={color}
        defaultValue={color}
        aria-label={`Colour for ${category}`}
      />
    </label>
  );
}
