/**
 * Waiting for a comparison to be built: an upload, or a re-root (§56).
 *
 * One loop for both, moved out of the upload panel when the re-root needed
 * the same thing — two copies of a backoff are two places for it to drift.
 */

import { api, ApiError } from "./client";
import type { ComparisonStatus } from "./types";

/**
 * Poll until the comparison leaves `pending`/`running`. Resolves on `ready`,
 * rejects with the job's reason on `failed`. `stopped` ends the wait early, for
 * a caller that has gone away; it then resolves without a final report.
 */
export async function poll(
  comparisonId: string,
  report: (status: ComparisonStatus) => void,
  stopped: () => boolean = () => false,
): Promise<void> {
  // Backs off so a long computation does not become a request every second for
  // several minutes.
  let wait = 500;
  for (;;) {
    if (stopped()) return;
    const status = await api.status(comparisonId);
    if (stopped()) return;
    report(status);
    if (status.status === "ready") return;
    if (status.status === "failed") {
      throw new ApiError(400, {
        detail: status.error ?? "The comparison failed.",
        code: "comparison_failed",
      });
    }
    await new Promise((resume) => setTimeout(resume, wait));
    wait = Math.min(wait * 1.5, 5_000);
  }
}
