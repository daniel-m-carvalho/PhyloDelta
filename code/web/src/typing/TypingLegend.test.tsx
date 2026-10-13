// @vitest-environment jsdom
/**
 * A category's colour is chosen from its legend swatch (§43).
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TypingLegend } from "./TypingLegend";

afterEach(() => {
  document.body.innerHTML = "";
});

function mount() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root: Root = createRoot(host);
  const onColor = vi.fn();
  const onResetColors = vi.fn();
  const show = (assignments: [string, string][], chosen: Record<string, string> = {}) =>
    act(() =>
      root.render(
        <TypingLegend
          assignments={new Map(assignments)}
          segmentKeys={["Source niche"]}
          keys={["Source niche"]}
          onSegmentKeys={() => {}}
          scale="log"
          onScale={() => {}}
          loading={false}
          error={null}
          chosen={chosen}
          onColor={onColor}
          onResetColors={onResetColors}
        />,
      ),
    );
  return { host, show, onColor, onResetColors };
}

const pickerFor = (host: HTMLElement, category: string) =>
  host.querySelector<HTMLInputElement>(`input[aria-label="Colour for ${category}"]`)!;

function choose(input: HTMLInputElement, value: string, events: string[]) {
  input.value = value;
  for (const type of events) input.dispatchEvent(new Event(type, { bubbles: true }));
}

describe("TypingLegend — choosing a category's colour", () => {
  it("applies the colour when it is committed, not on every step of a drag", () => {
    const { host, show, onColor } = mount();
    show([["Human", "#5c7cfa"], ["Food", "#12b886"]]);

    act(() => choose(pickerFor(host, "Human"), "#e03131", ["input", "input", "input"]));
    expect(onColor).not.toHaveBeenCalled();

    act(() => choose(pickerFor(host, "Human"), "#e03131", ["change"]));
    expect(onColor).toHaveBeenCalledTimes(1);
    expect(onColor).toHaveBeenCalledWith("Human", "#e03131");
  });

  it("still listens after a colour has been applied and the picker redrawn", () => {
    // The picker remounts when its colour changes; a listener left on the old
    // element would make the second choice do nothing.
    const { host, show, onColor } = mount();
    show([["Human", "#5c7cfa"]]);
    act(() => choose(pickerFor(host, "Human"), "#e03131", ["change"]));
    show([["Human", "#e03131"]], { Human: "#e03131" });

    act(() => choose(pickerFor(host, "Human"), "#000000", ["change"]));
    expect(onColor).toHaveBeenLastCalledWith("Human", "#000000");
    expect(onColor).toHaveBeenCalledTimes(2);
  });

  it("offers a reset only once a colour has been chosen", () => {
    const { host, show, onResetColors } = mount();
    show([["Human", "#5c7cfa"]]);
    expect(host.querySelector(".legend-reset")).toBeNull();

    show([["Human", "#e03131"]], { Human: "#e03131" });
    act(() => host.querySelector<HTMLButtonElement>(".legend-reset")!.click());
    expect(onResetColors).toHaveBeenCalledTimes(1);
  });
});
