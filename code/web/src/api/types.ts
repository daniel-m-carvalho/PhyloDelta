/**
 * The wire contract, as TypeScript.
 *
 * Hand-written rather than generated, deliberately: the surface is small, and
 * a generated client would bring a build step and a lot of types nothing uses.
 * These mirror `api/schemas.py` — if the two disagree, that file is right.
 *
 * Two conventions run through all of it (see the server's OpenAPI description):
 *
 * - **Node identity is the pre-order index in the stored tree.** One integer
 *   addresses a node in the topology, in a comparison, and in the next request.
 * - **Payloads are positional.** Parallel arrays in one agreed order; entry *k*
 *   of every array describes the same node. Comparison values for a slice line
 *   up index for index with its topology, so there is no join.
 */

export interface WhoAmI {
  owner_id: string;
  subject: string;
  issuer: string;
  email: string;
  display_name: string;
  mock: boolean;
}

export interface SliceNodes {
  /** Pre-order index in the STORED tree. The join key for everything else. */
  id: number[];
  /** Index into THESE arrays, or -1 at the slice root. Not a stored id. */
  parent: number[];
  label: string[];
  branch_len: (number | null)[];
  /** Leaves beneath this node in the FULL tree, not the number returned here. */
  true_leaf_count: number[];
  /** True where this tip stands for a clade that was not expanded. */
  truncated: boolean[];
}

export interface ComparisonValues {
  /** The node ids again, aligned with `nodes.id`. */
  id?: number[];
  /**
   * Which correspondence `similarity` and `corresponds` come from: "jaccard",
   * the shared one, or the name of the metric whose own was asked for (§52).
   */
  correspondence?: string;
  similarity: (number | null)[];
  corresponds: (number | null)[];
  /** RF's per-clade verdict; empty when the slice was asked under another metric. */
  exact?: boolean[];
  columns?: Record<string, (number | null)[]>;
}

export interface TreeSlice {
  tree: string;
  root: number;
  budget: number;
  displayed_leaves: number;
  hidden_leaves: number;
  total_leaves: number;
  /**
   * What became of the node `keep` asked to have drawn, when one was asked for.
   *
   * `keep` is best-effort: a clade needs room for two tips to be expanded
   * rather than drawn as a wedge, and a deep path from a distant root does not
   * get it. When it is missed the leaf is inside a wedge, and only the server
   * can say which one — a wedge's subtree is not in this response, so there is
   * nothing here to test containment against.
   */
  kept?: KeptNode | null;
  nodes: SliceNodes;
  comparison?: ComparisonValues | null;
}

export interface KeptNode {
  /** The node standing in: the one asked for where it was drawn, else its wedge. */
  node: number;
  /** False when `node` is an ancestor wedge rather than the node itself. */
  exact: boolean;
  /** The label of the node asked for — the only record of it when undrawn. */
  label: string;
}

export interface TreeSummary {
  id: string;
  /** What to call it; the id is a handle for URLs. Empty when none was given. */
  display_name: string;
  species: string;
  method: string;
  n_nodes: number;
  n_leaves: number;
  max_depth: number;
}

export interface PairSummary {
  id: string;
  /** The name given at upload, or "<left> vs <right>" by default. */
  display_name: string;
  left: string;
  right: string;
  species: string;
  same_species: boolean | null;
  label_match: string;
  shared_leaves: number;
  shared_fraction: number;
  caution: string | null;
  /** Every metric computed for this pair of trees. */
  metrics: string[];
  /**
   * The metric this entry is the comparison by (§52): a pair computed with
   * several is listed once for each. Empty from a server older than that.
   */
  metric?: string;
  /** Why this comparison could not be made, when it could not. */
  error?: string | null;
  status: "pending" | "running" | "ready" | "failed";
  /** The comparison this one re-roots, when a re-root made it (§56). */
  rerooted_from?: string | null;
  /** The re-rooted comparison made from this one, once ready (§56). */
  superseded_by?: string | null;
}

export interface IsolateSummary {
  species: string;
  n_rows: number;
  keys: string[];
}

export interface DatasetsResponse {
  trees: TreeSummary[];
  pairs: PairSummary[];
  isolates: IsolateSummary[];
}

export interface ComparisonSummary {
  pair: string;
  metric: string;
  left: string;
  right: string;
  /** Metric-specific scalars; free-form because metrics differ. */
  summary: Record<string, number | string>;
  shared_leaves: number;
  /** Leaf labels present only in one tree, so excluded from the metric. */
  dropped_from_left: string[];
  dropped_from_right: string[];
  same_species: boolean | null;
  caution: string | null;
}

export interface UploadAccepted {
  id: string;
  status: string;
  left_id: string;
  right_id: string;
  poll: string;
}

export interface ComparisonStatus {
  id: string;
  status: "pending" | "running" | "ready" | "failed";
  display_name: string;
  created_at: string;
  finished_at: string | null;
  error: string | null;
  ready: boolean;
  /** Metrics the upload asked for — the record of the request, not of the result. */
  metrics?: string[];
  /** Of those, the ones that can actually be asked for. */
  metrics_ready?: string[];
  /**
   * Metrics that were asked for and produced nothing, mapped to why.
   *
   * A comparison can be `ready` and still have entries here: one metric failing
   * does not spoil the rest, so it is served without that one. Absent data must
   * look absent — a metric quietly missing from the list is exactly the silent
   * default this project refuses.
   */
  metrics_failed?: Record<string, string>;
  /**
   * How each uploaded isolate table met its tree (§47); a side without a
   * table is absent. A table whose key named no leaf carries `error` and was
   * not used — the comparison is still ready.
   */
  isolates?: Partial<Record<"left" | "right", IsolateJoinReport>>;
  /** The comparison this one re-roots, when a re-root made it (§56). */
  rerooted_from?: string | null;
  /** What that re-root was. */
  reroot?: RerootInfo | null;
  /** A re-rooted comparison made from this one, once it is ready (§56). */
  superseded_by?: string | null;
}

/** A re-root, as the server recorded it (§56). */
export interface RerootInfo {
  from: string;
  side: "left" | "right";
  /** A stored id in the original's tree: the node the new root is above. */
  node: number;
  label: string;
  replace: boolean;
  /** The original's summary per metric, so the number before can be shown after. */
  before: Record<string, Record<string, number>>;
}

export interface RerootRequest {
  side: "left" | "right";
  node: number;
  replace?: boolean;
}

export interface RerootAccepted {
  id: string;
  status: string;
  rerooted_from: string;
  poll: string;
  reroot: RerootInfo;
}

export interface IsolateJoinReport {
  /** The column whose values name the tree's leaves. */
  key_column: string;
  rows: number;
  /** Rows whose key names no leaf. */
  rows_unmatched: number;
  /** Rows whose key cell is blank. */
  rows_without_key: number;
  /** Up to ten unmatched keys, sorted. */
  unmatched_examples: string[];
  leaves: number;
  leaves_without_rows: number;
  /** Why the table was not used; null when it was. */
  error: string | null;
}

/** Every failure from the API carries this shape. */
export interface ApiErrorBody {
  detail: string;
  code: string;
  hint: string | null;
  /** 410 `comparison_rerooted` only: what replaced it (§56). */
  moved_to?: string | null;
}


export interface FacetSummary {
  name: string;
  n_distinct: number;
  n_missing: number;
  segmentable: boolean;
}

export interface IsolateKeys {
  species: string;
  n_isolates: number;
  n_sequence_types: number;
  /** The column whose values name tree leaves (§47); `ST` for the demo tables. */
  key_column?: string;
  source: string;
  facets: FacetSummary[];
}

export interface ValueCount {
  value: string;
  count: number;
}

export interface LeafComposition {
  leaf: string;
  /** Isolates for this leaf that passed every filter. */
  total: number;
  /**
   * Isolates before filtering. `available === 0` means the leaf has no typing
   * data at all — true of 3.9% of vibrio leaves — which is different from
   * "filtered down to nothing", and a client should not draw them the same.
   */
  available: number;
  segments: ValueCount[];
}

export interface CompositionResponse {
  species: string;
  segment_by: string;
  filter: Record<string, string[]>;
  leaves: LeafComposition[];
}

/** The nearest ancestor of a node that is worth rooting a view at. */
export interface NodeContext {
  node: number;
  leaves: number;
  /** Levels walked up. 0 means the node already qualified. */
  climbed: number;
  /** The climb hit the root without meeting `min_leaves`. */
  reached_root: boolean;
}

/** One node whose label matched a search. */
export interface NodeMatch {
  /** Stored id — what `ancestor` and a slice's `keep` take. */
  node: number;
  /** The label as stored, which is what the panels draw. */
  label: string;
  /** The label is the query, ignoring case; otherwise it starts with it. */
  exact: boolean;
  /** False for a named internal node. */
  leaf: boolean;
  leaves: number;
}

/**
 * Nodes of ONE tree found by label (§37).
 *
 * An empty `matches` is an answer, not a failure: it is how a comparison
 * learns that a name is in one tree and not the other.
 */
export interface NodeSearch {
  tree: string;
  query: string;
  /** Every match; `matches` is the first `limit` of them. */
  total: number;
  /** Of `total`, how many are the query exactly. */
  exact: number;
  matches: NodeMatch[];
}

/** A comparison metric this server can compute, from GET /metrics. */
export interface MetricSummary {
  name: string;
  title: string;
  description: string;
  kind: string;
  /** False when the plugin is registered but its runtime is missing. */
  available: boolean;
  version: string;
  capabilities: Record<string, unknown>;
  /** Where its implementation comes from (§42); null when none is given. */
  reference?: MetricReference | null;
  /** What it contributes: labelled scalars, and per-node columns that say what they mean. */
  outputs?: { summary?: MetricScalar[]; columns: MetricColumn[] };
  /** The ways its result colours the trees, in the order to offer them (§52). */
  presentations?: Presentation[];
  /** The scalar its header shows, and what it is out of. */
  headline?: { key: string; of: string; to?: string } | null;
  /**
   * What colours its view (§52): "jaccard", the shared correspondence, or
   * "self", its own — served with `correspondence=metric`, and described by
   * its `similarity` column.
   */
  correspondence?: string;
}

/** One labelled summary scalar a metric declares. */
export interface MetricScalar {
  key: string;
  label: string;
  description: string;
}

/**
 * One way a metric's result colours the trees (§52).
 *
 * `gradient`: each branch by the comparison's `similarity`. `categories`: each
 * leaf by `column` — 0 or 1, named by `categories` — and a collapsed clade by
 * how many of its leaves are 1.
 */
export interface Presentation {
  name: string;
  label: string;
  kind: "gradient" | "categories";
  description: string;
  /** The first of `columns`; older servers send only this. */
  column: string;
  /** `categories`: disjoint count columns, one per category after the first. */
  columns?: string[];
  /** `categories[0]` names a leaf in none of `columns`; `categories[i]` one in `columns[i-1]`. */
  categories: string[];
  /** `gradient`: clades with fewer leaves have nothing to score, and are drawn grey. */
  min_leaves?: number;
  /** `gradient`: the colour bar's end labels, low end first; empty or absent for the app's own. */
  legend?: string[];
}

/** One per-node column a metric declares. */
export interface MetricColumn {
  name: string;
  dtype: string;
  semantics: string;
  label: string;
  description: string;
  render: string;
}

/** Where a metric's implementation comes from. */
export interface MetricReference {
  citation: string;
  doi: string;
  /** https://doi.org/<doi>, or "" without a DOI. */
  url: string;
}
