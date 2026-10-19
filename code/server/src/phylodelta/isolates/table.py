"""Reading an isolate table: TSV or CSV, and its header checked (§47).

One reader for the two places a table is read: the upload, which checks the
header the moment the bytes arrive, and the ingest, which reads every row. Two
readers would be two answers to "which column is this", and the upload would
accept a key the worker then could not find.

**The delimiter is decided by the first line**, the same rule as the browser's
header reader (``web/src/upload/tableHeader.ts``): a tab anywhere in it is TSV,
otherwise CSV. Not ``csv.Sniffer`` -- it guesses from a sample and has been
seen choosing a space or a letter; a rule the user can predict, and the client
applies identically, is worth more than a cleverer guess. A CSV with a tab
inside a quoted header name would be read as TSV; such a header refuses below
rather than joining on the wrong column.

**The header is checked by name**: empty column names, duplicated ones and an
unclosed quote each refuse with what was wrong. A duplicate is not cosmetic --
two columns called ``ST`` leave "join on ST" with two meanings.
"""

from __future__ import annotations

import csv
from pathlib import Path

# EnteroBase headers embed long parenthesised field lists; give csv room.
csv.field_size_limit(10**7)

#: How much of the file the header may take. EnteroBase's is ~4 KB; anything
#: without a newline in the first megabyte is not a table.
MAX_HEADER_BYTES = 1024 * 1024


class TableRejected(ValueError):
    """The table cannot be read as an isolate table. The message is for the user."""


def delimiter_of(first_line: str) -> str:
    return "\t" if "\t" in first_line else ","


def kind_of(delimiter: str) -> str:
    """'tsv' or 'csv', for the stored file's suffix and for messages."""
    return "tsv" if delimiter == "\t" else "csv"


def _check_header(header: list[str]) -> list[str]:
    names = [name.strip() for name in header]
    if len(names) < 2:
        raise TableRejected(
            "the header names one column; an isolate table needs the column that "
            "names the leaves and at least one other (is it tab- or comma-separated?)"
        )
    empty = [str(i + 1) for i, name in enumerate(names) if not name]
    if empty:
        raise TableRejected(f"column(s) {', '.join(empty)} have no name in the header")
    seen: set[str] = set()
    duplicated = [name for name in names if name in seen or seen.add(name)]
    if duplicated:
        raise TableRejected(
            f"the header names {', '.join(repr(n) for n in dict.fromkeys(duplicated))} "
            "more than once"
        )
    return names


def _parse_header(line: str) -> list[str]:
    delimiter = delimiter_of(line)
    # A quote still open at the end of the line would swallow the next lines
    # into one header cell; csv does not say so, it simply keeps reading.
    if _quote_left_open(line, delimiter):
        raise TableRejected("the header has an unclosed quote")
    return next(csv.reader([line], delimiter=delimiter))


def _quote_left_open(line: str, delimiter: str) -> bool:
    open_quote = False
    at_cell_start = True
    i = 0
    while i < len(line):
        c = line[i]
        if open_quote:
            if c == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    i += 1  # an escaped quote, still inside
                else:
                    open_quote = False
        elif c == '"' and at_cell_start:
            open_quote = True
        at_cell_start = c == delimiter and not open_quote
        i += 1
    return open_quote


def read_header(path: Path) -> tuple[list[str], str]:
    """The checked column names and the delimiter, reading only the first line."""
    with open(path, "rb") as handle:
        raw = handle.readline(MAX_HEADER_BYTES)
    if not raw.strip():
        raise TableRejected("the file is empty, or its first line is")
    if not raw.endswith(b"\n") and len(raw) >= MAX_HEADER_BYTES:
        raise TableRejected("no line break in the first megabyte; this is not a table")
    line = raw.decode("utf-8-sig", errors="replace").rstrip("\r\n")
    header = _parse_header(line)
    return _check_header(header), delimiter_of(line)


def read_table(path: Path) -> tuple[list[str], list[list[str]]]:
    """The checked header and every non-blank row."""
    _, delimiter = read_header(path)
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        header = _check_header(next(reader))
        rows = [row for row in reader if any(cell.strip() for cell in row)]
    return header, rows


def missing_key(column: str, header: list[str]) -> str:
    """The refusal for a key the header does not have, naming what it does."""
    shown = ", ".join(repr(name) for name in header[:12])
    more = f" and {len(header) - 12} more" if len(header) > 12 else ""
    return f"has no column {column!r}; its columns are {shown}{more}"
