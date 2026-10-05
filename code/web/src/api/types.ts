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
  similarity: (number | null)[];
  corresponds: (number | null)[];
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
  metrics: string[];
  status: "pending" | "running" | "ready" | "failed";
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
}

/** Every failure from the API carries this shape. */
export interface ApiErrorBody {
  detail: string;
  code: string;
  hint: string | null;
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
}
