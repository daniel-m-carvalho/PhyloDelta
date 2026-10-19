import { describe, expect, it } from "vitest";

import {
  initialKey,
  MAX_HEADER_BYTES,
  parseHeaderLine,
  readTableHeader,
  TableHeaderError,
} from "./tableHeader";

/*
 * The cases phylo-lens's header reader covers (ancillaryJoinColumn.ts), held
 * to the server's rules (isolates/table.py) so the two agree on every header.
 */
describe("parseHeaderLine", () => {
  it("reads a tab anywhere in the line as TSV", () => {
    expect(parseHeaderLine("ST\tcountry, region\tyear")).toEqual({
      columns: ["ST", "country, region", "year"],
      format: "tsv",
    });
  });

  it("reads a line without a tab as CSV", () => {
    expect(parseHeaderLine("isolate,ST,year\r\n")).toEqual({
      columns: ["isolate", "ST", "year"],
      format: "csv",
    });
  });

  it("drops a byte-order mark", () => {
    expect(parseHeaderLine("﻿ST,country").columns).toEqual(["ST", "country"]);
  });

  it("keeps a quoted comma inside its column and unescapes doubled quotes", () => {
    expect(parseHeaderLine('ST,"country, as ""reported""",year').columns).toEqual([
      "ST",
      'country, as "reported"',
      "year",
    ]);
  });

  it("trims names, as the server does", () => {
    expect(parseHeaderLine(" ST , country ").columns).toEqual(["ST", "country"]);
  });

  it.each([
    ["", "empty"],
    ["ST,,year", "Column 2 has no name"],
    ["ST,country,ST", '"ST" more than once'],
    ['ST,"country', "unclosed quote"],
    ["one-column", "names one column"],
  ])("refuses %j saying why", (line, why) => {
    expect(() => parseHeaderLine(line)).toThrow(TableHeaderError);
    expect(() => parseHeaderLine(line)).toThrow(why);
  });
});

describe("readTableHeader", () => {
  it("reads only up to the first line break", async () => {
    const file = new Blob(["ST\tcountry\n1\tPT\n2\t\"unclosed\n"]);
    await expect(readTableHeader(file)).resolves.toEqual({
      columns: ["ST", "country"],
      format: "tsv",
    });
  });

  it("finds a header longer than one chunk, and a character split across chunks", async () => {
    // EnteroBase headers are long; this one spans two 64 KB chunks with a
    // two-byte character straddling the boundary.
    const long = "x".repeat(64 * 1024 - 1) + "é";
    const file = new Blob([`ST,${long}\n1,2\n`]);
    const header = await readTableHeader(file);
    expect(header.columns).toEqual(["ST", long]);
  });

  it("takes a one-line file's only line as its header", async () => {
    await expect(readTableHeader(new Blob(["ST,country"]))).resolves.toMatchObject({
      columns: ["ST", "country"],
    });
  });

  it("refuses a file with no line break in its first megabyte", async () => {
    const file = new Blob(["a,".repeat(MAX_HEADER_BYTES)]);
    await expect(readTableHeader(file)).rejects.toThrow("not a table");
  });
});

describe("initialKey", () => {
  it("keeps the previous choice when this header has it", () => {
    expect(initialKey(["ST", "isolate"], "isolate")).toBe("isolate");
  });

  it("chooses ST otherwise", () => {
    expect(initialKey(["isolate", "ST"], "gone")).toBe("ST");
  });

  it("chooses nothing rather than guess when there is no ST", () => {
    expect(initialKey(["isolate", "country"], "")).toBe("");
  });
});
