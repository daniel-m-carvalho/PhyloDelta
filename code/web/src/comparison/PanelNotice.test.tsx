// @vitest-environment jsdom
/**
 * Why a panel did not move: said in the panel, and — for "not in this tree"
 * — gone on its own (§37.8).
 */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FADE_AFTER_MS, PanelNotice } from "./PanelNotice";

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

function mount() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  return {
    host,
    show: (text: string, fades: boolean, onDismiss: () => void) =>
      act(() => root.render(<PanelNotice text={text} fades={fades} onDismiss={onDismiss} />)),
  };
}

describe("PanelNotice", () => {
  it("says what it was given", () => {
    const { host, show } = mount();
    show("1203 is not in vibrio nj. This panel has not moved.", true, () => {});
    expect(host.textContent).toContain("1203 is not in vibrio nj");
  });

  it("goes away on its own when it is an answer", () => {
    const onDismiss = vi.fn();
    const { show } = mount();
    show("211 is not in vibrio nj. This panel has not moved.", true, onDismiss);

    act(() => vi.advanceTimersByTime(FADE_AFTER_MS - 1));
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("stays when it is a failure, until dismissed", () => {
    // A failed request that vanished while the user was looking at the other
    // panel would be an error they never saw.
    const onDismiss = vi.fn();
    const { host, show } = mount();
    show("Could not work out where that leaf sits.", false, onDismiss);

    act(() => vi.advanceTimersByTime(FADE_AFTER_MS * 10));
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => host.querySelector("button")!.click());
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("gives a new message its own time, not what was left of the last", () => {
    const onDismiss = vi.fn();
    const { show } = mount();
    show("211 is not in vibrio nj.", true, onDismiss);
    act(() => vi.advanceTimersByTime(FADE_AFTER_MS - 1000));
    show("4996 is not in vibrio nj.", true, onDismiss);
    act(() => vi.advanceTimersByTime(FADE_AFTER_MS - 1));
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
