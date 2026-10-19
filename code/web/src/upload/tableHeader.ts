/**
 * The column names of an isolate table, read in the browser (§47).
 *
 * Only the header line is read: it is what the key-column `<select>` needs,
 * and the table itself is joined on the server — a 12 MB file read in full to
 * fill one dropdown would be the browser doing the work the design keeps off
 * it. Lives in the web app, not the library: the library never sees a table,
 * only data already keyed by leaf.
 *
 * The rules are the server's (`isolates/table.py`), so a header accepted here
 * is accepted there: a tab anywhere in the first line is TSV, otherwise CSV;
 * a BOM is dropped; `""` inside quotes is one quote; and an empty name, a
 * duplicated name or an unclosed quote is refused, saying which.
 */

/** As the server's limit: no line break in this much is not a table. */
export const MAX_HEADER_BYTES = 1024 * 1024;
const CHUNK = 64 * 1024;

/** The key the demo tables use, and what is chosen when a header has it. */
export const DEFAULT_KEY_COLUMN = "ST";

export type TableFormat = "tsv" | "csv";

export interface TableHeader {
  columns: string[];
  format: TableFormat;
}

export class TableHeaderError extends Error {}

/** Parse one header line. Throws `TableHeaderError` with what was wrong. */
export function parseHeaderLine(raw: string): TableHeader {
  const line = raw.replace(/^﻿/, "").replace(/\r?\n$/, "").replace(/\r$/, "");
  if (!line.trim()) throw new TableHeaderError("The file is empty, or its first line is.");
  const format: TableFormat = line.includes("\t") ? "tsv" : "csv";
  const delimiter = format === "tsv" ? "\t" : ",";

  const cells: string[] = [];
  let cell = "";
  let quoted = false;
  let atCellStart = true;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (quoted) {
      if (c === '"' && line[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (c === '"') {
        quoted = false;
      } else {
        cell += c;
      }
    } else if (c === '"' && atCellStart) {
      quoted = true;
    } else if (c === delimiter) {
      cells.push(cell);
      cell = "";
    } else {
      cell += c;
    }
    atCellStart = !quoted && c === delimiter;
  }
  if (quoted) throw new TableHeaderError("The header has an unclosed quote.");
  cells.push(cell);

  const columns = cells.map((name) => name.trim());
  if (columns.length < 2) {
    throw new TableHeaderError(
      "The header names one column; an isolate table needs the column that names the " +
        "leaves and at least one other. Is it tab- or comma-separated?",
    );
  }
  const unnamed = columns.flatMap((name, i) => (name ? [] : [i + 1]));
  if (unnamed.length) {
    throw new TableHeaderError(`Column ${unnamed.join(", ")} has no name in the header.`);
  }
  const seen = new Set<string>();
  const repeated = new Set(columns.filter((name) => seen.has(name) || !seen.add(name)));
  if (repeated.size) {
    throw new TableHeaderError(
      `The header names ${[...repeated].map((name) => `"${name}"`).join(", ")} more than once.`,
    );
  }
  return { columns, format };
}

/**
 * Read the first line of a file and parse it.
 *
 * In chunks, stopping at the first line break: an EnteroBase header is ~4 KB,
 * so this usually reads one chunk of a 12 MB file. Bytes are gathered before
 * decoding so a character split across two chunks is not mangled.
 */
export async function readTableHeader(file: Blob): Promise<TableHeader> {
  const parts: Uint8Array[] = [];
  let length = 0;
  for (let offset = 0; offset < Math.min(file.size, MAX_HEADER_BYTES); offset += CHUNK) {
    const bytes = new Uint8Array(await file.slice(offset, offset + CHUNK).arrayBuffer());
    const newline = bytes.indexOf(0x0a);
    parts.push(newline === -1 ? bytes : bytes.subarray(0, newline));
    length += parts[parts.length - 1].length;
    if (newline !== -1) return parseHeaderLine(decode(parts, length));
  }
  if (file.size > MAX_HEADER_BYTES) {
    throw new TableHeaderError("No line break in the first megabyte; this is not a table.");
  }
  // A one-line file: its only line is the header, and it has no rows.
  return parseHeaderLine(decode(parts, length));
}

function decode(parts: Uint8Array[], length: number): string {
  const joined = new Uint8Array(length);
  let at = 0;
  for (const part of parts) {
    joined.set(part, at);
    at += part.length;
  }
  return new TextDecoder("utf-8").decode(joined);
}

/**
 * The column to pre-select: the one chosen before for this side, if this
 * header has it, else `ST`, else none — and then a choice is required rather
 * than the first column taken on the user's behalf.
 */
export function initialKey(columns: string[], previous: string): string {
  if (previous && columns.includes(previous)) return previous;
  if (columns.includes(DEFAULT_KEY_COLUMN)) return DEFAULT_KEY_COLUMN;
  return "";
}
