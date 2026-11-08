import type { TreeViewer } from "../viewer/tree_viewer";
import type { TreeOperator } from "./operator";

/** Where in the panel the button sits. */
export type Corner = "top-left" | "top-right" | "bottom-left" | "bottom-right";

export interface ResetViewOptions {
  /**
   * Default "top-left". A mirrored panel wants "top-right", so the two
   * buttons sit at the panels' outer corners, away from the gap between them.
   */
  corner?: Corner;
  /** Tooltip and accessible name. Default "Fit the tree to the panel". */
  title?: string;
}

/** Four corner brackets: the usual "fit to the frame" sign, no words needed. */
const ICON =
  '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" ' +
  'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
  '<path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4"/></svg>';

/**
 * A button that puts the tree back where it was fitted to the panel.
 *
 * **Shown only when there is somewhere to go back to.** Hidden at the fitted
 * view and after every render, which fits the tree afresh; shown as soon as a
 * zoom, a pan or a jump's centring moves the picture, and hidden again once
 * the camera is back. The viewer says which, on `cameraMoved` (judged in
 * screen pixels, so a sub-pixel settle does not show it).
 *
 * One click animates the camera to the fitted view (`TreeViewer.resetView`).
 * It never changes what is drawn, only where it is seen from: a collapsed
 * clade stays collapsed, a selection stays selected.
 */
export class ResetViewButton implements TreeOperator {
  readonly name = "reset-view";

  private viewer: TreeViewer | null = null;
  private unsubscribe: Array<() => void> = [];
  readonly element: HTMLButtonElement;

  constructor(options: ResetViewOptions = {}) {
    const corner = options.corner ?? "top-left";
    const title = options.title ?? "Fit the tree to the panel";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ptv-reset-view";
    button.title = title;
    button.setAttribute("aria-label", title);
    button.innerHTML = ICON;
    const [vertical, horizontal] = corner.split("-");
    Object.assign(button.style, {
      position: "absolute",
      [vertical]: "8px",
      [horizontal]: "8px",
      zIndex: "20", // over the overlays, like the legend
      display: "none",
      alignItems: "center",
      justifyContent: "center",
      width: "28px",
      height: "28px",
      padding: "0",
      border: "1px solid #ced4da",
      borderRadius: "6px",
      background: "rgba(255, 255, 255, 0.92)",
      color: "#495057",
      cursor: "pointer",
      boxShadow: "0 1px 3px rgba(0, 0, 0, 0.12)",
    } as Partial<CSSStyleDeclaration>);
    // A click on the button is not a click on the stage behind it.
    button.addEventListener("pointerdown", (event) => event.stopPropagation());
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      this.viewer?.resetView();
    });
    this.element = button;
  }

  attach(viewer: TreeViewer): void {
    this.viewer = viewer;
    viewer.getContainer().appendChild(this.element);
    this.unsubscribe.push(
      viewer.events.on("cameraMoved", ({ atFit }) => this.show(!atFit)),
      viewer.events.on("render", () => {
        // Sigma.kill() empties the container on rebuild; put the button back.
        const container = this.viewer?.getContainer();
        if (container && this.element.parentElement !== container) container.appendChild(this.element);
        // A render fits the tree afresh.
        this.show(false);
      }),
    );
  }

  detach(): void {
    this.unsubscribe.forEach((u) => u());
    this.unsubscribe = [];
    this.element.remove();
    this.viewer = null;
  }

  /** Whether the button is showing, for tests and for anyone asking. */
  isShown(): boolean {
    return this.element.style.display !== "none";
  }

  private show(on: boolean): void {
    this.element.style.display = on ? "flex" : "none";
  }
}
