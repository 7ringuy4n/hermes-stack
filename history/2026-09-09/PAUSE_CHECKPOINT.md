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

