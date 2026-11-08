// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { isSameView } from "../viewer/tree_viewer";
import { makeHarness, namedTree } from "./harness";
import { ResetViewButton } from "./reset_view";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("ResetViewButton — the way back to the fitted view", () => {
  function setup(options = {}) {
    const h = makeHarness(namedTree());
    const resetView = vi.fn();
    Object.assign(h.viewer, { resetView });
    const button = new ResetViewButton(options);
    button.attach(h.viewer);
    return { h, button, resetView };
  }

  it("is hidden until the view moves away from the fit, and hidden again once back", () => {
    const { h, button } = setup();
    expect(button.isShown()).toBe(false);
    h.viewer.events.emit("cameraMoved", { atFit: false });
    expect(button.isShown()).toBe(true);
    h.viewer.events.emit("cameraMoved", { atFit: true });
    expect(button.isShown()).toBe(false);
  });

  it("hides on a render, which fits the tree afresh, and stays in the panel", () => {
    const { h, button } = setup();
    h.viewer.events.emit("cameraMoved", { atFit: false });
    h.viewer.getContainer().innerHTML = ""; // what Sigma.kill() does on a rebuild
    h.render();
    expect(button.isShown()).toBe(false);
    expect(button.element.parentElement).toBe(h.viewer.getContainer());
  });

  it("asks the viewer to fit, and only that", () => {
    const { h, button, resetView } = setup();
    h.viewer.events.emit("cameraMoved", { atFit: false });
    button.element.click();
    expect(resetView).toHaveBeenCalledTimes(1);
  });

  it("sits in the corner asked for, with a name for screen readers and no text", () => {
    const { button } = setup({ corner: "top-right" });
    expect(button.element.style.top).toBe("8px");
    expect(button.element.style.right).toBe("8px");
    expect(button.element.style.left).toBe("");
    expect(button.element.getAttribute("aria-label")).toBe("Fit the tree to the panel");
    expect(button.element.textContent).toBe("");
    expect(button.element.querySelector("svg")).not.toBeNull();
  });

  it("is removed with the operator", () => {
    const { h, button } = setup();
    button.detach();
    expect(h.viewer.getContainer().contains(button.element)).toBe(false);
    h.viewer.events.emit("cameraMoved", { atFit: false });
    expect(button.isShown()).toBe(false);
  });
});

describe("isSameView — a move is what the eye can see", () => {
  const fitted = { x: 0.5, y: 0.5, ratio: 1.3, angle: 0 };

  it("ignores a sub-pixel settle, at any zoom", () => {
    // 0.0004 of the frame at 1,000 px per unit is 0.4 px: not a move.
    expect(isSameView({ ...fitted, x: 0.5004 }, fitted, 1000)).toBe(true);
  });

  it("sees a pan of a pixel or more, a zoom of 1% or more", () => {
    expect(isSameView({ ...fitted, y: 0.502 }, fitted, 1000)).toBe(false);
    expect(isSameView({ ...fitted, ratio: 1.3 * 1.02 }, fitted, 1000)).toBe(false);
    expect(isSameView({ ...fitted, ratio: 1.3 * 1.005 }, fitted, 1000)).toBe(true);
  });
});
