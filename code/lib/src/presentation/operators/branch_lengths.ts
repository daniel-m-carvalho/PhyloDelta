import type Sigma from "sigma";
import type { TreeViewer } from "../viewer/tree_viewer";
import type { TreeOperator } from "./operator";

/**
 * A branch length as it is written beside the branch (§44): up to three
 * decimals, trailing zeros dropped — 0.5, 1.235, 12. A length that would
 * round to zero is written as "<0.001" rather than "0", which would claim the
 * branch has no length when it only has very little; an NJ tree's small
 * negative lengths keep their sign the same way.
 */
export function formatBranchLength(length: number): string {
  if (length === 0) return "0";
  if (Math.abs(length) < 0.0005) return length > 0 ? "<0.001" : ">-0.001";
  return String(Number(length.toFixed(3)));
}

export interface BranchLengthOptions {
  /** Draw the labels (default false: they are opt-in, like every overlay). */
  enabled?: boolean;
  /** Text for a length. Default {@link formatBranchLength}. */
  format?: (length: number) => string;
  /** CSS font. Default 10px system sans-serif. */
  font?: string;
  /** Text colour. Default a muted grey, so labels read as annotation, not ink. */
  color?: string;
}

/** Space kept clear either side of a label, in CSS pixels. */
const PAD = 3;
/** A label's height for the overlap test: the 10px font plus a little air. */
const LINE = 12;

/**
 * Writes each branch's length beside it (§44), in either layout.
 *
 * **Only where it fits.** A slice can hold 600 tips, and a label on every
 * branch is a smear of overlapping numbers. A label is drawn only when its
 * branch is drawn wider on screen than the text, so zooming in reveals more of
 * them and nothing ever overlaps the branch it does not belong to. Nor another
 * label: where rows sit closer than a line of text, the second label of a pair
 * is left out rather than printed over the first. Decided per
 * frame, from screen positions, which is why this is drawn on `afterRender`
 * rather than through the graph's reducers: those run when the graph is
 * processed, not when the camera moves.
 *
 * **Not Sigma's edge labels.** Sigma draws an edge's label only when both its
 * extremities have visible labels, and a branch here runs between invisible
 * connector points, so none would ever show.
 *
 * Reads `branchLength`, which the layout puts on the edge that draws each
 * branch: the real length, so a log-scaled phylogram still says how long a
 * branch really is.
 */
export class BranchLengthPresenter implements TreeOperator {
  readonly name = "branch-lengths";

  private viewer: TreeViewer | null = null;
  private renderer: Sigma | null = null;
  private unsubscribe: Array<() => void> = [];
  private canvas: HTMLCanvasElement;
  private afterRender = () => this.draw();

  private enabled: boolean;
  private format: (length: number) => string;
  private font: string;
  private color: string;

  constructor(options: BranchLengthOptions = {}) {
    this.enabled = options.enabled ?? false;
    this.format = options.format ?? formatBranchLength;
    this.font = options.font ?? "10px ui-sans-serif, system-ui, sans-serif";
    this.color = options.color ?? "#6b7180";

    this.canvas = document.createElement("canvas");
    Object.assign(this.canvas.style, {
      position: "absolute",
      inset: "0",
      width: "100%",
      height: "100%",
      pointerEvents: "none", // annotation: clicks belong to the Sigma canvas
      zIndex: "11", // under the wedges and bar charts, over the branches
    } as CSSStyleDeclaration);
  }

  attach(viewer: TreeViewer): void {
    this.viewer = viewer;
    viewer.getContainer().appendChild(this.canvas);
    this.unsubscribe.push(viewer.events.on("render", ({ renderer }) => this.onRender(renderer)));
  }

  detach(): void {
    this.unsubscribe.forEach((u) => u());
    this.unsubscribe = [];
    this.renderer?.off("afterRender", this.afterRender);
    this.renderer = null;
    this.canvas.remove();
    this.viewer = null;
  }

  setEnabled(on: boolean): void {
    this.enabled = on;
    this.draw();
  }

  isEnabled(): boolean {
    return this.enabled;
  }

  private onRender(renderer: Sigma): void {
    // Sigma.kill() empties the container on rebuild; re-attach the overlay.
    const container = this.viewer?.getContainer();
    if (container && this.canvas.parentElement !== container) container.appendChild(this.canvas);
    this.renderer?.off("afterRender", this.afterRender);
    this.renderer = renderer;
    renderer.on("afterRender", this.afterRender);
    this.draw();
  }

  /** Labels drawn on the last frame, for tests and for anyone asking. */
  private drawn = 0;
  drawnCount(): number {
    return this.drawn;
  }

  private draw(): void {
    this.drawn = 0;
    const container = this.viewer?.getContainer();
    const context = this.canvas.getContext("2d");
    if (!container || !context) return;

    const width = container.clientWidth;
    const height = container.clientHeight;
    const ratio = window.devicePixelRatio || 1;
    if (this.canvas.width !== Math.round(width * ratio) || this.canvas.height !== Math.round(height * ratio)) {
      this.canvas.width = Math.round(width * ratio);
      this.canvas.height = Math.round(height * ratio);
    }
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    if (!this.enabled || !this.renderer) return;

    const renderer = this.renderer;
    const graph = renderer.getGraph();
    context.font = this.font;
    context.fillStyle = this.color;
    context.textAlign = "center";
    context.textBaseline = "bottom";

    const taken: Array<{ left: number; right: number; top: number; bottom: number }> = [];
    graph.forEachEdge((_edge, attributes, _source, _target, sourceAttrs, targetAttrs) => {
      const length = attributes.branchLength;
      if (typeof length !== "number") return;
      const a = renderer.graphToViewport({ x: sourceAttrs.x as number, y: sourceAttrs.y as number });
      const b = renderer.graphToViewport({ x: targetAttrs.x as number, y: targetAttrs.y as number });
      if (a.y < 0 || a.y > height) return; // off screen vertically
      const left = Math.max(0, Math.min(a.x, b.x));
      const right = Math.min(width, Math.max(a.x, b.x));
      const text = this.format(length);
      const needed = context.measureText(text).width + 2 * PAD;
      if (right - left < needed) return; // does not fit: leave the branch bare
      const centre = (left + right) / 2;
      const box = {
        left: centre - needed / 2,
        right: centre + needed / 2,
        top: a.y - 2 - LINE,
        bottom: a.y - 2,
      };
      // A label already there wins: this one would only be printed over it.
      if (taken.some((t) => box.left < t.right && t.left < box.right && box.top < t.bottom && t.top < box.bottom)) {
        return;
      }
      taken.push(box);
      context.fillText(text, centre, a.y - 2);
      this.drawn += 1;
    });
  }
}
