// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { KeyColumn, keyReady, sharedColumns } from "./UploadPanel";

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
const other = new File(["strain\tST\n"], "other.tsv");
const header = { columns: ["isolate", "ST", "country"], format: "csv" as const };
const otherHeader = { columns: ["strain", "ST", "isolate"], format: "tsv" as const };

describe("KeyColumn", () => {
  it("is disabled until a file has been read", () => {
    const host = render(<KeyColumn tables={[]} value="" onChange={() => {}} />);
    expect(host.querySelector("select")!.disabled).toBe(true);
    expect(host.textContent).toContain("Choose a file first");
  });

  it("offers every column of one table, with the chosen one selected", () => {
    const host = render(<KeyColumn tables={[{ file, header }]} value="ST" onChange={() => {}} />);
    const select = host.querySelector("select")!;
    expect(select.disabled).toBe(false);
    expect(select.value).toBe("ST");
    expect([...select.options].slice(1).map((o) => o.value)).toEqual(["isolate", "ST", "country"]);
  });

  it("offers only the columns two tables share", () => {
    const host = render(
      <KeyColumn tables={[{ file, header }, { file: other, header: otherHeader }]} value="ST" onChange={() => {}} />,
    );
    const select = host.querySelector("select")!;
    expect([...select.options].slice(1).map((o) => o.value)).toEqual(["isolate", "ST"]);
    expect(host.textContent).toContain("CSV and TSV, 2 columns in both");
  });

  it("waits for the second table before offering anything", () => {
    const host = render(
      <KeyColumn tables={[{ file, header }, { file: other }]} value="ST" onChange={() => {}} />,
    );
    expect(host.querySelector("select")!.disabled).toBe(true);
    expect(host.textContent).toContain("Reading…");
  });

  it("says so when two tables share no column", () => {
    const apart = { columns: ["strain", "host"], format: "tsv" as const };
    const host = render(
      <KeyColumn tables={[{ file, header }, { file: other, header: apart }]} value="" onChange={() => {}} />,
    );
    expect(host.querySelector("select")!.disabled).toBe(true);
    expect(host.textContent).toContain("no column in common");
  });

  it("asks for a choice when none is made", () => {
    const host = render(<KeyColumn tables={[{ file, header }]} value="" onChange={() => {}} />);
    expect(host.querySelector("select")!.value).toBe("");
    expect(host.textContent).toContain("Choose the column whose values are the trees' leaf labels");
  });

  it("shows why a header was refused, and whose", () => {
    const host = render(
      <KeyColumn
        tables={[{ file, header }, { file: other, error: "The header has an unclosed quote." }]}
        value=""
        onChange={() => {}}
      />,
    );
    expect(host.textContent).toContain("Right table: The header has an unclosed quote.");
    expect(host.querySelector("select")!.disabled).toBe(true);
  });
});

describe("sharedColumns and keyReady", () => {
  it("need nothing when there is no table", () => {
    expect(sharedColumns([])).toBeNull();
    expect(keyReady([], "")).toBe(true);
  });

  it("need every header read and the key in all of them", () => {
    expect(keyReady([{ file }], "ST")).toBe(false);
    expect(keyReady([{ file, header }], "")).toBe(false);
    expect(keyReady([{ file, header }], "strain")).toBe(false);
    expect(keyReady([{ file, header }], "isolate")).toBe(true);
    expect(keyReady([{ file, header }, { file: other, header: otherHeader }], "country")).toBe(false);
    expect(keyReady([{ file, header }, { file: other, header: otherHeader }], "ST")).toBe(true);
  });
});
