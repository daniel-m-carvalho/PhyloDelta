// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import type { MetricSummary } from "../api/types";
import { UploadPanel } from "./UploadPanel";

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

const metric = (name: string, title: string, available = true) =>
  ({ name, title, available, reason: available ? "" : "not installed" }) as unknown as MetricSummary;

async function render(metrics: MetricSummary[] | undefined) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => root.render(<UploadPanel onReady={() => {}} metrics={metrics} />));
  return { host, root };
}

describe("UploadPanel", () => {
  it("offers the metrics the app already has, without asking the server again", async () => {
    // The v0.2.0 campaign found /metrics fetched twice on opening the app,
    // once by the app and once here: Table 19's data nearly doubled.
    const asked = vi.spyOn(api, "metrics");
    const { host } = await render([metric("rf", "Robinson-Foulds"), metric("spr", "SPR", false)]);
    expect(asked).not.toHaveBeenCalled();
    const options = [...host.querySelectorAll("option")].map((o) => o.textContent ?? "");
    expect(options.some((t) => t.includes("Robinson-Foulds"))).toBe(true);
    expect(options.some((t) => t.includes("SPR"))).toBe(true);
  });

  it("fills in once the app's list arrives", async () => {
    const asked = vi.spyOn(api, "metrics");
    const { host, root } = await render(undefined);
    expect(host.textContent).not.toContain("Robinson-Foulds");
    await act(async () =>
      root.render(<UploadPanel onReady={() => {}} metrics={[metric("rf", "Robinson-Foulds")]} />),
    );
    expect([...host.querySelectorAll("option")].some((o) => o.textContent?.includes("Robinson-Foulds"))).toBe(true);
    expect(asked).not.toHaveBeenCalled();
  });
});
