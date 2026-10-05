/**
 * Why a panel did not move, said inside that panel (§37.8).
 *
 * One place for every jump that could not land: a search whose name is in the
 * other tree only, a menu jump to a leaf with no counterpart, a request that
 * failed. In the panel rather than in a modal, because the other panel may
 * just have moved, and a dialog over both would hide the half that worked.
 */

import { useEffect } from "react";

/**
 * How long "not in this tree" stays. Long enough to read a sentence twice;
 * short enough that it is gone by the time the user has looked at the other
 * panel and back.
 */
export const FADE_AFTER_MS = 6000;

export function PanelNotice({
  text,
  fades,
  onDismiss,
}: {
  text: string;
  /** False for a failure, which stays until dismissed. */
  fades: boolean;
  onDismiss: () => void;
}) {
  // Restarted by a new message: a second "not in this tree" for a different
  // name gets its own six seconds, not what was left of the first's.
  useEffect(() => {
    if (!fades) return;
    const timer = setTimeout(onDismiss, FADE_AFTER_MS);
    return () => clearTimeout(timer);
  }, [text, fades, onDismiss]);

  return (
    <div className={fades ? "panel-popup fading" : "panel-popup error"} role="status">
      <span>{text}</span>
      <button
        type="button"
        className="found-clear"
        onClick={onDismiss}
        aria-label="Dismiss"
        title="Dismiss"
      >
        ×
      </button>
    </div>
  );
}
