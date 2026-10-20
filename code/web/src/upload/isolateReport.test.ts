import { describe, expect, it } from "vitest";

import type { IsolateJoinReport } from "../api/types";
import { describeJoin, describeJoins, describeKey, unusedTables } from "./isolateReport";

const clean: IsolateJoinReport = {
  key_column: "ST",
  rows: 26629,
  rows_unmatched: 0,
  rows_without_key: 0,
  unmatched_examples: [],
  leaves: 3000,
  leaves_without_rows: 0,
  error: null,
};

describe("describeJoin", () => {
  it("says only what joined when everything did", () => {
    expect(describeJoin("left", clean)).toBe(`Left: ${(26629).toLocaleString()} rows joined on "ST"`);
  });

  it("names what did not match, with examples", () => {
    const line = describeJoin("right", {
      ...clean,
      rows_unmatched: 312,
      unmatched_examples: ["1001", "1002", "1003", "1004"],
      rows_without_key: 1,
      leaves_without_rows: 1,
    });
    expect(line).toContain("312 match no leaf (e.g. 1001, 1002, 1003, …)");
    expect(line).toContain("1 has no key");
    expect(line).toContain("1 leaf has no rows");
  });

  it("says a table was not used, and why", () => {
    const line = describeJoin("left", { ...clean, error: "no value in column 'ST' names a leaf" });
    expect(line).toBe("Left isolate data not used: no value in column 'ST' names a leaf");
  });
});

describe("describeJoins and unusedTables", () => {
  it("cover the sides that had a table, left first", () => {
    const right = { ...clean, error: "nothing matched" };
    expect(describeJoins({ right, left: clean })).toHaveLength(2);
    expect(describeJoins({ right, left: clean })[0]).toMatch(/^Left/);
    expect(unusedTables({ right, left: clean })).toEqual(["Right isolate data not used: nothing matched"]);
    expect(describeJoins(undefined)).toEqual([]);
  });
});

describe("describeKey", () => {
  it("names the key once when both sides share it", () => {
    const name = { ...clean, key_column: "Name", rows_unmatched: 26239 };
    expect(describeKey({ left: name, right: name })).toBe('Matched to the leaves by the column "Name"');
    expect(describeKey({ left: name })).toBe('Matched to the leaves by the column "Name"');
  });

  it("names both when an API client keyed each table on its own column", () => {
    expect(describeKey({ left: { ...clean, key_column: "Name" }, right: clean })).toBe(
      'Matched to the leaves by "Name" on the left and "ST" on the right',
    );
  });

  it("leaves out a table that was not used, and is null with none", () => {
    expect(describeKey({ left: clean, right: { ...clean, key_column: "x", error: "nothing matched" } })).toBe(
      'Matched to the leaves by the column "ST"',
    );
    expect(describeKey({ left: { ...clean, error: "nothing matched" } })).toBeNull();
    expect(describeKey(undefined)).toBeNull();
  });
});
