/**
 * Find a node by name in both trees at once (§37).
 *
 * Asks the server, one request per tree, because neither panel can answer:
 * each holds its tree as a slice of a few dozen nodes. The answers are merged
 * by label so a row says where the name exists *before* it is picked — a name
 * in one tree only is visible as such in the list, not discovered afterwards.
 */

import { useEffect, useRef, useState } from "react";

import { api, ApiError } from "../api/client";
import { mergeByLabel, type SearchResult, type SearchRow } from "./search";

/** Long enough that typing "1203" asks once, not four times. */
const DEBOUNCE_MS = 200;
/** Per tree. The list is for reading; `total` says how many more there are. */
const LIMIT = 20;

export function SearchBox({
  trees,
  onPick,
}: {
  /** Both panels' trees, left then right: the id to ask with, the name to show. */
  trees: [{ id: string; name: string }, { id: string; name: string }];
  onPick: (row: SearchRow, failed: SearchResult["failed"]) => void;
}) {
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const wait = setTimeout(() => setQuery(text.trim()), DEBOUNCE_MS);
    return () => clearTimeout(wait);
  }, [text]);

  // Keyed by the ids and the query — strings, compared by value. The trees
  // prop is a fresh array on every render, and depending on it would re-run
  // this on each one: the shape of the loop `useTypingData` has had three
  // times (see CLAUDE.md's open threads).
  const [leftId, rightId] = [trees[0].id, trees[1].id];
  useEffect(() => {
    if (!query) {
      setResult(null);
      return;
    }
    const abort = new AbortController();
    const ask = (treeId: string) =>
      api.search(treeId, query, { limit: LIMIT, signal: abort.signal }).then(
        (answer) => ({ answer, failed: null }),
        (failed: unknown) => ({
          answer: null,
          failed: failed instanceof ApiError ? failed.message : String(failed),
        }),
      );
    void Promise.all([ask(leftId), ask(rightId)]).then(([left, right]) => {
      if (abort.signal.aborted) return;
      setResult({
        query,
        rows: mergeByLabel(left.answer, right.answer),
        totals: [left.answer?.total ?? 0, right.answer?.total ?? 0],
        failed: [left.failed, right.failed],
      });
      setOpen(true);
    });
    return () => abort.abort();
  }, [query, leftId, rightId]);

  // A click anywhere else closes the list, as a menu would.
  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  const pick = (row: SearchRow) => {
    if (!result) return;
    setOpen(false);
    onPick(row, result.failed);
  };

  const current = result && result.query === text.trim() ? result : null;

  return (
    <div className="search" ref={box}>
      <input
        type="search"
        className="search-input"
        placeholder="Find a node by name, e.g. an ST"
        aria-label="Find a node by name in both trees"
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            // Claimed, so it closes this and does not also clear a mark.
            event.preventDefault();
            setOpen(false);
          } else if (event.key === "Enter" && current?.rows[0]) {
            pick(current.rows[0]);
          }
        }}
      />
      {open && text.trim() ? (
        <div className="search-results" role="listbox">
          {!current ? (
            <p className="search-note">Searching…</p>
          ) : (
            <Results result={current} trees={trees} onPick={pick} />
          )}
        </div>
      ) : null}
    </div>
  );
}

function Results({
  result,
  trees,
  onPick,
}: {
  result: SearchResult;
  trees: [{ name: string }, { name: string }];
  onPick: (row: SearchRow) => void;
}) {
  const { rows, totals, failed } = result;
  return (
    <>
      {failed.map((reason, side) =>
        reason ? (
          <p key={side} className="search-note error">
            Could not search {trees[side].name}: {reason}
          </p>
        ) : null,
      )}
      {rows.length === 0 && !failed[0] && !failed[1] ? (
        <p className="search-note">
          No node called “{result.query}”, or starting with it, in either tree.
        </p>
      ) : null}
      {rows.length ? (
        <table className="search-table">
          <thead>
            <tr>
              <th>Name</th>
              <th title={trees[0].name}>Left</th>
              <th title={trees[1].name}>Right</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.label}
                role="option"
                aria-selected="false"
                className="search-row"
                onClick={() => onPick(row)}
              >
                <td>
                  <strong>{row.label}</strong>
                  {kindOf(row)}
                </td>
                {row.sides.map((nodes, side) => (
                  <td key={side} className={nodes.length ? "search-in" : "search-out"}>
                    {failed[side] ? "?" : nodes.length ? "✓" : "✗"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {totals.some((total) => total > rows.length) ? (
        <p className="search-note">
          Showing the first {rows.length}: {totals[0].toLocaleString()} in left,{" "}
          {totals[1].toLocaleString()} in right. Type more to narrow it.
        </p>
      ) : null}
    </>
  );
}

/**
 * Said only when the match is not a plain leaf. A named internal node is a
 * clade, and jumping to it marks a clade — the user should know that before
 * picking it, not wonder afterwards why no single tip lit up.
 */
function kindOf(row: SearchRow) {
  const nodes = [...row.sides[0], ...row.sides[1]];
  const clade = nodes.find((node) => !node.leaf);
  const repeated = row.sides.some((side) => side.length > 1);
  if (!clade && !repeated) return null;
  return (
    <span className="search-kind">
      {clade ? ` · clade of ${clade.leaves.toLocaleString()} leaves` : null}
      {repeated ? " · on more than one node; the first is shown" : null}
    </span>
  );
}
