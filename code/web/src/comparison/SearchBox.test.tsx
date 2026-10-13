// @vitest-environment jsdom
/**
 * The search box asks both trees once per query, and says where a name is
 * before it is picked.
 *
 * The request count is asserted because this codebase has had three effects
 * that re-fired on every render (CLAUDE.md, open threads); a search box that
 * did it would hammer two endpoints per keystroke and show nothing wrong.
 */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { NodeSearch } from "../api/types";
import { SearchBox } from "./SearchBox";

const TREES: [{ id: string; name: string }, { id: string; name: string }] = [
  { id: "left-tree", name: "Left tree" },
  { id: "right-tree", name: "Right tree" },
];

function answer(tree: string, labels: string[], query = "1203"): NodeSearch {
  return {
    tree,
    query,
    total: labels.length,
    exact: labels.filter((label) => label === query).length,
    matches: labels.map((label, i) => ({
      node: i + (tree === "left-tree" ? 100 : 500),
      label,
      exact: label === query,
      leaf: true,
      leaves: 1,
    })),
  };
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.useFakeTimers();
  fetchMock = vi.fn(async (url: string) => {
    const tree = url.includes("/trees/left-tree/") ? "left-tree" : "right-tree";
    const labels = tree === "left-tree" ? ["1203", "12030"] : ["12031"];
    return new Response(JSON.stringify(answer(tree, labels)), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

function mount(onPick = vi.fn()) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const render = () =>
    act(() => {
      // A fresh `trees` array each time, as the real parent passes one.
      root.render(<SearchBox trees={[{ ...TREES[0] }, { ...TREES[1] }]} onPick={onPick} />);
    });
  render();
  return { host, render, onPick };
}

async function type(host: HTMLElement, text: string) {
  const input = host.querySelector("input")!;
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    setter.call(input, text);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(250);
  });
}

describe("SearchBox", () => {
  it("asks each tree once per query, however often the parent re-renders", async () => {
    const { host, render } = mount();
    await type(host, "1203");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    render();
    render();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls.some((url) => url.includes("/trees/left-tree/search?q=1203"))).toBe(true);
    expect(urls.some((url) => url.includes("/trees/right-tree/search?q=1203"))).toBe(true);
  });

  it("shows, per name, which tree has it", async () => {
    const { host } = mount();
    await type(host, "1203");
    const rows = [...host.querySelectorAll(".search-row")].map((row) =>
      [...row.querySelectorAll("td")].map((cell) => cell.textContent),
    );
    expect(rows).toEqual([
      ["1203", "✓", "✗"],
      ["12030", "✓", "✗"],
      ["12031", "✗", "✓"],
    ]);
  });

  it("hands the picked row to the view, with each side's node", async () => {
    const { host, onPick } = mount();
    await type(host, "1203");
    await act(async () => {
      host.querySelector<HTMLElement>(".search-row")!.click();
    });
    expect(onPick).toHaveBeenCalledTimes(1);
    const [row, failed] = onPick.mock.calls[0];
    expect(row.label).toBe("1203");
    expect(row.sides[0][0].node).toBe(100);
    expect(row.sides[1]).toEqual([]);
    expect(failed).toEqual([null, null]);
  });

  it("says plainly when neither tree has the name", async () => {
    fetchMock.mockImplementation(
      async (url: string) =>
        new Response(
          JSON.stringify(answer(url.includes("left") ? "left-tree" : "right-tree", [], "999999")),
          { status: 200 },
        ),
    );
    const { host } = mount();
    await type(host, "999999");
    expect(host.textContent).toContain("No node called “999999”");
  });

  it("reports a failed side as failed, never as absent", async () => {
    fetchMock.mockImplementation(async (url: string) =>
      url.includes("right-tree")
        ? new Response(
            JSON.stringify({ detail: "No tree 'right-tree'.", code: "tree_not_found", hint: null }),
            { status: 404 },
          )
        : new Response(JSON.stringify(answer("left-tree", ["1203"])), { status: 200 }),
    );
    const { host } = mount();
    await type(host, "1203");
    expect(host.textContent).toContain("Could not search Right tree");
    const cells = [...host.querySelectorAll(".search-row td")].map((cell) => cell.textContent);
    expect(cells).toEqual(["1203", "✓", "?"]);
  });
});
