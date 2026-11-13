// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { CladeShapePresenter } from "./clade_shape";
import { ComparisonOperator } from "./comparison";
import { ExpandCollapseOperator } from "./expand_collapse";
import { binaryTree, makeHarness, namedTree } from "./harness";
import type { NewickNode } from "../tree/types";

/** Wedges are CSS-border triangles: zero-size divs with a border-*. */
function wedges(container: HTMLElement): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>("div")].filter(
    (el) => el.style.borderTop?.includes("solid") && el.style.width === "0px"
  );
}

describe("CladeShapePresenter", () => {
  it("draws no wedge when nothing is collapsed", () => {
    const h = makeHarness(namedTree());
    new CladeShapePresenter().attach(h.viewer);
    h.render();
    expect(wedges(h.container)).toHaveLength(0);
  });

  it("draws a wedge for each collapsed clade", () => {
    const h = makeHarness(namedTree());
    new CladeShapePresenter().attach(h.viewer);
    h.viewer.setCollapseFn((n) => n.name === "b");
    h.render();

    expect(wedges(h.container)).toHaveLength(1);
  });

  it("scales the wedge with the number of leaves hidden", () => {
    const small = makeHarness(binaryTree(2)); // 4 leaves
    const large = makeHarness(binaryTree(6)); // 64 leaves
    for (const h of [small, large]) {
      new CladeShapePresenter().attach(h.viewer);
      h.viewer.setCollapseFn((n) => !!n.branchset?.length && n !== h.viewer.getTree());
      h.render();
    }

    const heightOf = (h: typeof small) =>
      parseFloat(wedges(h.container)[0].style.borderTop);

    expect(heightOf(large)).toBeGreaterThan(heightOf(small));
  });

  it("reports the true hidden leaf count, not the pruned one", () => {
    // The displayed clade is a clone with no children; the count must come from
    // `origin`, i.e. the real subtree behind the tip.
    const h = makeHarness(binaryTree(5)); // 32 leaves
    new CladeShapePresenter().attach(h.viewer);
    h.viewer.setCollapseFn((n) => n === h.viewer.getTree()!.branchset![0]);
    h.render();

    expect(wedges(h.container)[0].title).toBe("16 leaves");
  });

  it("makes the collapsed marker transparent but keeps it clickable", () => {
    // Deliberately transparent rather than size 0: Sigma hit-tests by size, and
    // this overlay is pointer-events:none, so zeroing would destroy the only
    // click target for expanding the clade.
    const h = makeHarness(namedTree());
    new CladeShapePresenter().attach(h.viewer);
    h.viewer.setCollapseFn((n) => n.name === "b");
    h.render();

    const style = h.styleOf("named_b");
    expect(style.color).toBe("rgba(0,0,0,0)");
    expect(style.size).toBeGreaterThan(0); // still hit-testable
  });

  it("leaves the marker visible when hideMarker is false", () => {
    const h = makeHarness(namedTree());
    new CladeShapePresenter({ hideMarker: false }).attach(h.viewer);
    h.viewer.setCollapseFn((n) => n.name === "b");
    h.render();

    expect(h.styleOf("named_b").color).not.toBe("rgba(0,0,0,0)");
  });

  it("points the apex the other way when reflected", () => {
    const normal = makeHarness(namedTree(), { reflect: false });
    const mirrored = makeHarness(namedTree(), { reflect: true });
    for (const h of [normal, mirrored]) {
      new CladeShapePresenter().attach(h.viewer);
      h.viewer.setCollapseFn((n) => n.name === "b");
      h.render();
    }

    const w1 = wedges(normal.container)[0];
    const w2 = wedges(mirrored.container)[0];
    // One uses border-right for the apex, the other border-left.
    expect(!!w1.style.borderRight).not.toBe(!!w2.style.borderRight);
  });

  it("works from collapse state driven by the collapse operator", () => {
    // The two operators share no reference — the presenter reads isCollapsed
    // off the layout nodes (README §9.3).
    const h = makeHarness(binaryTree(4));
    const collapse = new ExpandCollapseOperator();
    collapse.attach(h.viewer);
    new CladeShapePresenter().attach(h.viewer);

    collapse.setDepth(1, false);
    h.render();

    expect(wedges(h.container).length).toBeGreaterThan(0);
  });

  it("removes its overlay on detach", () => {
    const h = makeHarness(namedTree());
    const shapes = new CladeShapePresenter();
    shapes.attach(h.viewer);
    h.viewer.setCollapseFn((n) => n.name === "b");
    h.render();
    expect(wedges(h.container)).toHaveLength(1);

    shapes.detach();
    expect(wedges(h.container)).toHaveLength(0);
  });
});

describe("sizing wedges in a server-summarised view", () => {
  /**
   * The failure this guards: a view holding 50 leaves that stands for 17,645.
   * Calibrating to the 50 makes every wedge hiding more than that saturate,
   * so a clade of twelve and a clade of eight thousand draw identically —
   * which defeats the only thing a wedge has to say.
   */
  it("distinguishes a small hidden clade from a huge one", () => {
    const presenter = new CladeShapePresenter({});
    const at = (leaves: number, standsFor: number): number =>
      // @ts-expect-error probing the private scale deliberately: it is the
      // behaviour under test, and exposing it would widen the public API for
      // a test's convenience.
      presenter.heightFor(leaves, standsFor);

    // Calibrated to what the view stands for, every size is distinguishable.
    expect(at(8_441, 17_645)).toBeGreaterThan(at(400, 17_645));
    expect(at(400, 17_645)).toBeGreaterThan(at(12, 17_645));

    // Calibrated to the 50 leaves locally present, everything at or above 50
    // pins to the top of the scale: a clade of 400 and one of 8,441 draw
    // identically, and the wedge stops carrying information.
    expect(at(400, 50)).toBeCloseTo(at(8_441, 50), 5);
  });
});

describe("colouring wedges by value", () => {
  it("calls a colour function with the real clade, not the pruned clone", () => {
    const h = makeHarness(binaryTree(5)); // 32 leaves
    const seen: number[] = [];
    new CladeShapePresenter({
      color: (node) => {
        seen.push(node.branchset?.length ?? 0);
        return "#ff00ff";
      },
    }).attach(h.viewer);
    h.viewer.setCollapseFn((n) => n === h.viewer.getTree()!.branchset![0]);
    h.render();

    // The clone has no children; only `origin` does. A zero here would mean the
    // function cannot see the subtree it is supposed to describe.
    expect(seen).toEqual([2]);
    expect(wedges(h.container)[0].style.borderRight).toContain("rgb(255, 0, 255)");
  });

  it("falls back to the node's own colour when the function declines", () => {
    const h = makeHarness(namedTree());
    new CladeShapePresenter({ color: () => undefined }).attach(h.viewer);
    h.viewer.setCollapseFn((n) => n.name === "b");
    h.render();

    const side = wedges(h.container)[0].style.borderRight;
    expect(side).toBeTruthy();
    expect(side).not.toContain("undefined");
  });

  it("redraws on setColor, since a presentation switch fires no render", () => {
    const h = makeHarness(namedTree());
    const shape = new CladeShapePresenter({ color: "#000000" });
    shape.attach(h.viewer);
    h.viewer.setCollapseFn((n) => n.name === "b");
    h.render();
    expect(wedges(h.container)[0].style.borderRight).toContain("rgb(0, 0, 0)");

    shape.setColor(() => "#ffd400");
    expect(wedges(h.container)[0].style.borderRight).toContain("rgb(255, 212, 0)");
  });

  describe("a located node's mark on a collapsed clade", () => {
    // Reported from use: marking a clade put a magenta ball beside a black
    // triangle. The comparison highlight painted the marker this presenter had
    // hidden; the triangle, which is what represents the clade, never changed.
    function marked() {
      const h = makeHarness(namedTree());
      const shape = new CladeShapePresenter();
      shape.attach(h.viewer);
      // Attached after the presenter, as createComparison does — which is what
      // let its highlight override the hidden marker.
      const cmp = new ComparisonOperator({
        enabled: true,
        keyOf: (n) => n.name ?? "",
        highlightColor: "#d400ff",
        persistHighlight: true,
      });
      cmp.attach(h.viewer);
      cmp.drawMarkWith((node, color) => shape.mark(node, color));
      h.viewer.setCollapseFn((n) => n.name === "b");
      h.render();
      return { h, shape, cmp };
    }
    const apex = (h: ReturnType<typeof makeHarness>) => wedges(h.container)[0].style.borderRight;

    it("recolours the wedge and leaves the marker hidden", () => {
      const { h, cmp } = marked();
      const own = apex(h);

      expect(cmp.highlightByNode("named_b", { center: false, flash: false })).toBe(true);
      expect(apex(h)).toContain("rgb(212, 0, 255)");
      expect(h.styleOf("named_b").color).toBe("rgba(0,0,0,0)");

      cmp.clearHighlight();
      expect(apex(h)).toBe(own);
    });

    it("survives a re-render, which rebuilds every wedge", () => {
      const { h, cmp } = marked();
      cmp.highlightByNode("named_b", { center: false, flash: false });
      h.render();
      expect(apex(h)).toContain("rgb(212, 0, 255)");
      expect(h.styleOf("named_b").color).toBe("rgba(0,0,0,0)");
    });

    it("still marks a leaf on its marker, where there is no wedge", () => {
      const { h, cmp } = marked();
      const own = apex(h);
      cmp.highlightByNode("named_a", { center: false, flash: false });
      expect(h.styleOf("named_a").color).toBe("#d400ff");
      expect(apex(h)).toBe(own);
    });

    it("moves off the wedge when the mark moves to a leaf", () => {
      const { h, cmp } = marked();
      const own = apex(h);
      cmp.highlightByNode("named_b", { center: false, flash: false });
      cmp.highlightByNode("named_a", { center: false, flash: false });
      expect(apex(h)).toBe(own);
      expect(h.styleOf("named_a").color).toBe("#d400ff");
    });
  });
});

describe("CladeShapePresenter — scale and reference (§55.2)", () => {
  /** A root with one collapsed child per size, each a caterpillar of that many leaves. */
  function clades(sizes: number[]): NewickNode {
    const clade = (n: number, tag: string): NewickNode =>
      n === 1
        ? { name: `${tag}_0`, length: 1 }
        : { name: `${tag}`, length: 1, branchset: Array.from({ length: n }, (_, i) => ({ name: `${tag}_${i}`, length: 1 })) };
    return { name: "root", branchset: sizes.map((n, i) => clade(n, `c${i}`)) };
  }

  /** Half-height of each wedge, keyed by the leaves it hides. */
  function heights(options: ConstructorParameters<typeof CladeShapePresenter>[0], sizes: number[]) {
    const h = makeHarness(clades(sizes), { maxNodes: 10_000 });
    new CladeShapePresenter({ minHalfHeight: 2, maxHalfHeight: 12, ...options }).attach(h.viewer);
    h.viewer.setCollapseFn((n) => !!n.branchset?.length && n !== h.viewer.getTree());
    h.render();
    const out = new Map<number, number>();
    for (const el of wedges(h.container)) {
      out.set(parseInt(el.title.replace(/,/g, ""), 10), parseFloat(el.style.borderTop));
    }
    return out;
  }

  it("grows linearly with the leaves hidden under the linear scale", () => {
    const sizes = [2, 4, 8, 16];
    const got = heights({ scale: "linear", saturateAt: 16 }, sizes);
    for (const n of sizes) expect(got.get(n)).toBeCloseTo(2 + (n / 16) * 10, 6);
    // Equal steps in leaves are equal steps in height.
    expect(got.get(8)! - got.get(4)!).toBeCloseTo((got.get(16)! - got.get(8)!) / 2, 6);
  });

  it("grows with log2 of the leaves hidden under the log scale, the default", () => {
    const sizes = [2, 4, 8, 16];
    for (const options of [{ scale: "log" as const, saturateAt: 16 }, { saturateAt: 16 }]) {
      const got = heights(options, sizes);
      for (const n of sizes) expect(got.get(n)).toBeCloseTo(2 + (Math.log2(n) / 4) * 10, 6);
    }
  });

  it("gives the largest drawn wedge the full height under largest-drawn", () => {
    for (const scale of ["linear", "log"] as const) {
      const got = heights({ scale, reference: "largest-drawn" }, [3, 5, 9]);
      expect(got.get(9)).toBeCloseTo(12, 6);
      expect(got.get(3)!).toBeLessThan(12);
    }
    // Against the view instead, nothing on screen reaches the top: the tree
    // stands for 17 leaves and its largest clade hides 9.
    expect(heights({ scale: "linear", reference: "view" }, [3, 5, 9]).get(9)!).toBeLessThan(12);
  });

  it("is the library's old behaviour when nothing is asked for", () => {
    const sizes = [2, 6, 30];
    expect(heights({}, sizes)).toEqual(heights({ scale: "log", reference: "view" }, sizes));
  });

  it("switches scale on a live panel", () => {
    const h = makeHarness(clades([2, 8]), { maxNodes: 10_000 });
    const shape = new CladeShapePresenter({ minHalfHeight: 2, maxHalfHeight: 12, saturateAt: 8 });
    shape.attach(h.viewer);
    h.viewer.setCollapseFn((n) => !!n.branchset?.length && n !== h.viewer.getTree());
    h.render();
    const of2 = () => wedges(h.container).find((el) => el.title === "2 leaves")!;
    const logHeight = parseFloat(of2().style.borderTop);
    shape.setScale("linear");
    expect(parseFloat(of2().style.borderTop)).toBeCloseTo(2 + (2 / 8) * 10, 6);
    expect(parseFloat(of2().style.borderTop)).not.toBeCloseTo(logHeight, 3);
  });

  it("never lets two neighbouring wedges overlap with fitRows, however close the rows", () => {
    const sizes = Array.from({ length: 40 }, (_, i) => 2 + ((i * 37) % 200));
    const h = makeHarness(clades(sizes), { maxNodes: 100_000 });
    new CladeShapePresenter({
      minHalfHeight: 2, maxHalfHeight: 40, scale: "linear", reference: "largest-drawn", fitRows: true,
    }).attach(h.viewer);
    h.viewer.setCollapseFn((n) => !!n.branchset?.length && n !== h.viewer.getTree());
    h.render();
    const spans = wedges(h.container)
      .map((el) => {
        const top = parseFloat(el.style.top);
        return [top, top + 2 * parseFloat(el.style.borderTop)] as const;
      })
      .sort((a, b) => a[0] - b[0]);
    expect(spans).toHaveLength(40);
    for (let i = 1; i < spans.length; i++) expect(spans[i][0]).toBeGreaterThanOrEqual(spans[i - 1][1]);
  });
});

describe("CladeShapePresenter — hover count (§55.2)", () => {
  it("says how many leaves a hovered wedge hides, and goes away on leaving", () => {
    const h = makeHarness(binaryTree(5)); // 32 leaves
    new CladeShapePresenter({ hoverCount: true }).attach(h.viewer);
    h.viewer.setCollapseFn((n) => n === h.viewer.getTree()!.branchset![0]);
    h.render();
    const id = [...h.viewer.getNodeMap().values()].find((n) => n.isCollapsed)!.id;
    const tooltip = () =>
      [...h.container.querySelectorAll<HTMLElement>("div")].find((el) => el.textContent === "16 leaves");

    h.viewer.events.emit("enterNode", { node: id });
    expect(tooltip()?.style.display).toBe("block");
    h.viewer.events.emit("leaveNode", {});
    expect(tooltip()?.style.display).toBe("none");
  });

  it("says nothing over a node that is not a wedge, or when not asked to", () => {
    const h = makeHarness(binaryTree(3));
    new CladeShapePresenter().attach(h.viewer);
    h.viewer.setCollapseFn((n) => n === h.viewer.getTree()!.branchset![0]);
    h.render();
    const id = [...h.viewer.getNodeMap().values()].find((n) => n.isCollapsed)!.id;
    h.viewer.events.emit("enterNode", { node: id });
    expect(h.container.textContent).not.toContain("leaves");
  });
});
