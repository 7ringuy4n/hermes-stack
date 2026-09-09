# Release gate pause checkpoint — 2026-09-09 16:53 +07:00

## Scope and revision

- Branch: `codex/fix/zalo-generic-composed-schedules`
- Tested source candidate: `0dcb8a1cbcc8f2df7104955ed37ba33ddfd4aa63`
- VPS checkout: `/opt/assistant`
- No merge request has been created or merged. Production branches remain
  unchanged.
- Do not record the SSH password, Zalo account id, group id, or exported router
  secrets in this repository. Resolve the authorized runtime target from the
  existing protected VPS configuration when resuming.

## Verified before the pause

- A clean destroy and full-feature deploy completed after verified backups.
- The three-member `test` group, requesting account membership, seven OmniRouter
  combos, AI-box configuration, two Hermes replicas, and expected workers were
  preserved.
- Focused live gates passed for scheduled composed images, flexible Da Nang
  layout, archive extraction, DM/group concurrency and quotes, two concurrent
  search-plus-DOCX requests, remote-video refusal, and eight-message FIFO
  continuity.
- The authoritative full case-index run printed and passed cases `1/131`
  through `116/131`, including:
  - `113/131` scheduled composed image;
  - `114/131` flexible composed layout;
  - `115/131` file-pipeline security;
  - `116/131` Grafana integration.
- The requested pause signal arrived while `117/131` was executing. Its child
  was interrupted and printed `FAIL(1)`; this is invalid interrupted evidence,
  not an accepted product failure. Case 118 began and was immediately
  interrupted. Neither case 117 nor any later case is counted as verified by
  this run.
- Because `run_case_index_lab.py` writes its Markdown summary only after the
  entire matrix completes, the on-disk summary at pause time still represented
  an older failed attempt. It must not be used as release evidence.

## Preserved worktree state

Generated and modified report artifacts were saved with:

`stash@{0}: pause-after-case-114-final-vps-gate-2026-09-09`

The stash contains the modified old case-index summary and the generated
scheduled/flexible-layout report directories. Leave it stashed for audit; do
not pop it over a new successful report. The worktree was clean before this
checkpoint file was added.

## Resume procedure

1. Read the mandatory repository rules and histories again, including this
   checkpoint.
2. Confirm the VPS still has two Hermes replicas, the expected workers, one
   logged-in Zalo bridge with a live SSE owner, an empty message queue, the
   three-member `test` group, and seven OmniRouter combos. Do not print secrets
   or raw account/group identifiers into reports.
3. Inspect recent Docker, per-replica Hermes, OmniRouter, Router Worker,
   Dispatcher, and Zalo journal logs from the pause boundary. Separate expected
   test fault injection and transient provider errors from real application
   failures.
4. Rerun `defaults_routers_lab.py` (case 21) first because its previous process
   was interrupted. Investigate any reproducible failure before continuing.
5. Run the complete 131-case index again from the beginning with VPS-local mode,
   candidate SHA `0dcb8a1cbcc8f2df7104955ed37ba33ddfd4aa63`, a 900-second
   per-case timeout, and the protected runtime Zalo target. A new uninterrupted
   zero-failure summary is required; the partial run cannot authorize release.
6. Copy the successful VPS summary into
   `test/reports/run-case-index-lab/SUMMARY.md`, verify its candidate stamp and
   `Fails: 0`, update the dated verification history, and commit only the valid
   evidence.
7. Only after the full matrix and log audit pass: create and merge the request
   to `develop`, create and merge the request to `main`, reconcile other open
   merge requests while retaining the newest conflicting change, and provide
   the documented main-branch update instructions.

## Second pause checkpoint — 2026-09-09 21:10 +07:00

### New committed candidates

- `6359c29` stops a claimed rich document from falling through to an older
  embedded image sidecar.
- `7b60e04` preserves the restrictive repository Office wrappers.
- `9ac1998` isolates the visual-PDF result parser from live SSH dependencies.
- `6d72f83` records bundled `pdf`, `docx`, and `xlsx` names in each replica's
  `.curator_suppressed` file before image-level skill sync and strengthens the
  rendered-PDF release oracle.
- `27c24bf` defines current-condition practical tips as unrequested
  recommendations and adds a deterministic scope regression check.

Both Hermes replicas were updated through `bash run.sh update hermes` after
verified backups. Each active replica retained `pdf-tools-local`, contained the
three curator suppression entries, and had no categorized or `official` PDF
duplicate. No merge request has been created or merged.

### Focused verification

The first collision-free focused PDF run produced one readable document, no
acknowledged image sidecar, and a 9/10 page without blocking visual defects, but
it added a practical-advice strip. The strengthened scope contract and oracle
then rejected that pattern. A second focused run on `27c24bf` passed with one
current-observation-only PDF, no image sidecar, an 8/10 rendered-page score,
and no blocking overlap, clipping, or unreadable content.

### Interrupted 132-case run

Adding the separately counted visual-PDF parser unit expanded the current case
index from 131 to 132. The latest run passed cases `1/132` through `110/132`.
Case `111/132` (`zalo_tn_visual_weather_pdf_inject.py`) failed because no new
PDF appeared within its 240-second artifact window. Its durable image-delivery
audit succeeded with count zero; this was not a sidecar regression.

Hermes logs show that the request entered the safe file-generation path, ran
search, then a terminal action waited for approval and ended after roughly 314
seconds with `BLOCKED: Command timed out without user response`. The agent turn
finished after roughly 402 seconds, after the case oracle had already returned.
Case `112/132` began while that stale agent turn was still active and failed;
treat it as contaminated downstream evidence until rerun in isolation. Case
`113/132` was interrupted immediately at the user's pause request and is not
valid evidence. No test-script process remained after interruption, and the
incomplete run did not write a new authoritative case-index summary.

### Resume from this point

1. Re-read all mandatory repository rules and histories, including this
   checkpoint. Use candidate `27c24bf8649ffa5c48d4dddd69350ea60bbc41bf`.
2. Inspect the Router Worker/Omni request trace for the case-111 terminal call
   around the recorded failure boundary. Determine why an ordinary authorized
   Dispatcher office-file call entered a user-approval wait. Fix the core
   routing/tool contract rather than extending the artifact deadline blindly.
3. Recheck queue/session drainage, Zalo SSE ownership, both Hermes replicas,
   and the absence of bundled Office-skill duplicates. Rerun case 111 and the
   latency case independently before starting another matrix.
4. Run the complete numbered 132-case matrix from the beginning with a
   900-second per-case process timeout and the protected runtime target. Require
   a new uninterrupted `Fails: 0` summary; the partial run is not release
   evidence.
5. Complete the full Docker/Hermes/Zalo/OmniRouter/Router Worker/Dispatcher log
   audit, commit valid evidence, and only then follow the develop/main merge
   sequence from the earlier resume procedure.
