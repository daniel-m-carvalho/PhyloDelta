// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { MetricReferences } from "./MetricReferences";

afterEach(() => {
  document.body.innerHTML = "";
});

function render(node: React.ReactElement) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  act(() => createRoot(host).render(node));
  return host;
}

describe("MetricReferences", () => {
  it("says what each paper is the reference for, and links its DOI", () => {
    const host = render(
      <MetricReferences
        references={[
          { citation: "Robinson & Foulds 1981.", role: "metric", doi: "10.1016/x", url: "https://doi.org/10.1016/x" },
          { citation: "Branco, Vaz & Francisco 2024.", role: "implementation", doi: "", url: "" },
        ]}
      />,
    );
    const items = [...host.querySelectorAll("li")].map((li) => li.textContent);
    expect(items[0]).toContain("Defined in Robinson & Foulds 1981.");
    expect(items[1]).toContain("Computed as in Branco, Vaz & Francisco 2024.");
    const links = [...host.querySelectorAll("a")];
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("href")).toBe("https://doi.org/10.1016/x");
    expect(links[0].getAttribute("target")).toBe("_blank");
  });

  it("draws nothing for a metric without references", () => {
    expect(render(<MetricReferences references={[]} />).innerHTML).toBe("");
  });
});
