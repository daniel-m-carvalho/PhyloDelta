// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { MetricReferenceLine } from "./MetricReferences";

afterEach(() => {
  document.body.innerHTML = "";
});

function render(node: React.ReactElement) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  act(() => createRoot(host).render(node));
  return host;
}

describe("MetricReferenceLine", () => {
  it("says where the implementation comes from, with its DOI link", () => {
    const host = render(
      <MetricReferenceLine
        reference={{ citation: "Branco, Vaz & Francisco 2024.", doi: "10.3390/y", url: "https://doi.org/10.3390/y" }}
      />,
    );
    expect(host.textContent).toContain("Computed as in Branco, Vaz & Francisco 2024.");
    const links = [...host.querySelectorAll("a")];
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["https://doi.org/10.3390/y"]);
    expect(links[0].getAttribute("target")).toBe("_blank");
  });

  it("shows no link without a DOI", () => {
    const host = render(<MetricReferenceLine reference={{ citation: "A program.", doi: "", url: "" }} />);
    expect(host.querySelector("a")).toBeNull();
  });

  it("draws nothing for a metric without a reference", () => {
    expect(render(<MetricReferenceLine reference={null} />).innerHTML).toBe("");
  });
});
