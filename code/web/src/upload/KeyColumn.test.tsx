// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { KeyColumn, tableReady } from "./UploadPanel";

afterEach(() => {
  document.body.innerHTML = "";
});

function render(node: React.ReactElement) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  act(() => createRoot(host).render(node));
  return host;
}

const file = new File(["ST,country\n"], "meta.csv");
const header = { columns: ["isolate", "ST", "country"], format: "csv" as const };

describe("KeyColumn", () => {
  it("is disabled until a file has been read", () => {
    const host = render(<KeyColumn read={{ file: undefined }} value="" onChange={() => {}} />);
    expect(host.querySelector("select")!.disabled).toBe(true);
    expect(host.textContent).toContain("Choose a file first");
  });

  it("offers every column of the header, with the chosen one selected", () => {
    const host = render(<KeyColumn read={{ file, header }} value="ST" onChange={() => {}} />);
    const select = host.querySelector("select")!;
    expect(select.disabled).toBe(false);
    expect(select.value).toBe("ST");
    expect([...select.options].slice(1).map((o) => o.value)).toEqual(["isolate", "ST", "country"]);
  });

  it("asks for a choice when none is made", () => {
    const host = render(<KeyColumn read={{ file, header }} value="" onChange={() => {}} />);
    expect(host.querySelector("select")!.value).toBe("");
    expect(host.textContent).toContain("Choose the column whose values are the tree's leaf labels");
  });

  it("shows why a header was refused", () => {
    const host = render(
      <KeyColumn read={{ file, error: "The header has an unclosed quote." }} value="" onChange={() => {}} />,
    );
    expect(host.textContent).toContain("unclosed quote");
    expect(host.querySelector("select")!.disabled).toBe(true);
  });
});

describe("tableReady", () => {
  it("needs nothing when there is no table", () => {
    expect(tableReady(undefined, { file: undefined }, "")).toBe(true);
  });

  it("needs the header read and a key it has", () => {
    expect(tableReady(file, { file }, "ST")).toBe(false);
    expect(tableReady(file, { file, header }, "")).toBe(false);
    expect(tableReady(file, { file, header }, "strain")).toBe(false);
    expect(tableReady(file, { file, header }, "isolate")).toBe(true);
  });
});
