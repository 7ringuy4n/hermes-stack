# Agent Operations Rules --- hermes-stack

**Audience:** Cursor agents and human operators working on this
repository.\
**Source of truth:** This file at the repository root.\
**Lab methodology:** [`test/RULES.md`](./test/RULES.md)\
**Git workflow:** [`docs/GIT.md`](./docs/GIT.md)\
**Change history:** [`docs/CHANGELOG.md`](./docs/CHANGELOG.md)

> These rules govern agent behavior. Do not hardcode them into
> application runtime messages, prompts, adapters, or business logic.

------------------------------------------------------------------------

## 1. Mission

You are an AI/DevOps/Developer responsible for maintaining and improving
this system for long-term production and enterprise use.

Priorities:

1.  Correctness
2.  Security and data protection
3.  Architectural integrity
4.  Root-cause resolution
5.  Reliability and fault tolerance
6.  Performance and concurrency
7.  Maintainability and reusability
8.  Memory efficiency
9.  Operational simplicity

**Never sacrifice correctness or architectural integrity merely to make
the current test, request, or deployment succeed.**

------------------------------------------------------------------------

## 2. Rule Priority

When rules appear to conflict, apply them in this order:

1.  Security and data protection
2.  Source-of-truth and architecture integrity
3.  Test integrity
4.  Root-cause correctness
5.  Production safety
6.  Reliability
7.  Performance
8.  Maintainability
9.  Convenience

A lower-priority optimization must never violate a higher-priority rule.

------------------------------------------------------------------------

## 3. Hard Gates

The following are mandatory and must be satisfied before finishing work:

-   Never weaken, delete, bypass, or manipulate tests to obtain a
    passing result.
-   Never leave a lab-only hotpatch as the permanent fix.
-   Never fix a production bug only on the VPS.
-   **If an error or bug is found, fix it in the durable setup
    file / script / source of truth** (`scripts/main/`, `run.sh`,
    compose, `.env.example`, product code). **Do not cheat by making
    patch files**, one-off `*.patch` / hotpatch scripts, VPS-only
    sed overlays, or session-only workarounds that leave the setup
    path broken for the next install.
-   Never use special-case logic solely for the observed failing input.
-   Never bypass an available real integration when the requirement is
    to test that integration.
-   Never leave test-only configuration enabled after testing.
-   Never introduce lab identity, credentials, or host-specific secrets
    into committed source.
-   **Always ask the user before creating merge requests** (or pushing
    / deploying). Never open, merge, or push an MR without explicit
    permission in the current conversation.
-   Never bypass security, authorization, validation, or isolation
    merely to make a workflow succeed.
-   Never claim success without verifying the affected behavior.
-   Never replace a root-cause fix with a workaround unless the
    workaround is explicitly architecturally justified and documented.
-   Never finish a lab test run or bridge/host patch without monitoring
    for crash-loops and abnormal logs (Hermes container + Zalo bridge
    unit at minimum). See §18 / §19 and
    [`scripts/HISTORY.md`](./scripts/HISTORY.md) entry
    **2026-08-21 11:20 +07 — Bridge crash-loop on :8787**.
-   **After done** (session complete or abandoned): **clean up all
    generated scripts for the current session in development** under
    gitignored paths such as `scripts/temp/` and `hermes/temp/` —
    leave only durable, committed tooling. Do not leave VPS-only patch
    scripts or credential extractors behind.

------------------------------------------------------------------------

## 4. Root Cause & Recurrence Prevention

When a bug, failing test, abnormal behavior, regression, or
production/lab issue is discovered:

1.  Reproduce the failure.
2.  Identify the underlying root cause.
3.  Fix the root cause in the original repository source.
4.  Add or update a regression test.
5.  Add at least one meaningful variant of the original failure when
    practical.
6.  Run the affected tests and relevant regression tests.
7.  Verify that the solution does not depend on temporary state, manual
    intervention, test-only configuration, or a single exact input.
8.  Verify that the same class of failure is addressed, not merely the
    reported instance.

### Prohibited Symptom-Only Fixes

Do not introduce:

-   exact-input special cases;
-   hardcoded request IDs;
-   test-specific branches;
-   host-specific branches;
-   user-specific branches;
-   phrase-specific workarounds;
-   arbitrary delays;
-   arbitrary retries;
-   forced fallbacks;
-   fake success responses;
-   disabled validation;
-   weakened assertions;
-   bypassed integrations;
-   configuration changes whose only purpose is to make the current
    failure disappear.

Such mechanisms are allowed only when they are part of the intended
architecture and their behavior is explicitly justified.

A fix is incomplete if the original failure disappears but the
underlying failure class can still recur.

------------------------------------------------------------------------

## 5. Test Integrity

Tests are evidence of system correctness, not obstacles to bypass.

Never:

-   modify a test only to make it pass;
-   remove assertions;
-   reduce coverage;
-   weaken expected results;
-   bypass validation;
-   mock away the behavior being tested;
-   skip a real integration path;
-   replace realistic user behavior with artificial input solely for
    convenience.

Before changing a test:

1.  Inspect the current implementation.
2.  Inspect the current architecture.
3.  Determine whether the architecture intentionally changed.
4.  If architecture changed, update the test to represent the new
    architecture.
5.  Otherwise, fix the implementation.

Tests must validate the intended system behavior, not merely the
implementation's ability to satisfy the test.

------------------------------------------------------------------------

## 6. Architecture Alignment

After any:

-   rearchitecture;
-   refactoring;
-   component replacement;
-   API change;
-   workflow change;
-   responsibility change;
-   worker change;
-   routing change;

review all affected tests and documentation.

Do not preserve obsolete tests merely because they pass.

If a test becomes obsolete, replace it with an equivalent test covering
the intended behavior through the current production architecture.

------------------------------------------------------------------------

## 7. Real Integration Testing

When a supported external integration is available and
authenticated/configured, applicable end-to-end tests must use the real
integration path.

For Zalo:

``` text
Real user
  → Zalo
  → zalo-proxy
  → Hermes
```

Do not bypass the integration by directly calling an internal service
when the purpose of the test is to validate Zalo behavior.

If the external integration is genuinely unavailable, direct Hermes
testing may be used while preserving the same expected user behavior.

Never modify or weaken a test simply to avoid an available integration.

------------------------------------------------------------------------

## 8. LLM-First Content Understanding

Application code must not implement natural-language understanding.

Do not use application code for:

-   intent classification;
-   semantic parsing;
-   entity extraction;
-   natural-language interpretation;
-   multilingual phrase matching;
-   large keyword dictionaries;
-   hardcoded natural-language patterns.

Use the appropriate LLM / Model Router and structured output.

Application code should handle deterministic responsibilities such as:

-   validation;
-   authorization;
-   persistence;
-   queueing;
-   scheduling;
-   locking;
-   serialization;
-   rate limiting;
-   execution.

**LLM understands; application code validates and executes.**

String operations are allowed for deterministic formats and protocols.

------------------------------------------------------------------------

## 9. Intent Classification

Intent classification must support:

-   natural language;
-   multilingual input;
-   paraphrases;
-   previously unseen expressions;
-   ambiguous requests.

Do not add keyword exceptions to fix individual false positives.

When classification is wrong, improve:

1.  classifier;
2.  prompt;
3.  skill;
4.  intent schema;
5.  model/router configuration.

When ambiguous, return structured uncertainty and request clarification
rather than guessing.

Deterministic keyword matching is permitted only for:

-   explicit commands;
-   security boundaries;
-   protocol markers;
-   intentionally exact-match operations.

When changing classification, test:

-   true positives;
-   true negatives;
-   false positives;
-   false negatives;
-   multilingual variants;
-   paraphrases;
-   unrelated requests.

------------------------------------------------------------------------

## 10. Skills Before New Application Logic

If a requirement can be implemented by an existing or new Agent Skill:

1.  Inspect the relevant skill first.
2.  Reuse it when appropriate.
3.  Create a reusable skill when necessary.
4.  Do not invent application code for behavior that belongs in the
    skill layer.

Prefer:

``` text
Skill + configuration
```

over:

``` text
new hardcoded application logic
```

------------------------------------------------------------------------

## 11. Configuration Over Hardcoding

Do not hardcode:

-   user-facing messages;
-   large keyword lists;
-   secret-probe patterns;
-   bad-word lists;
-   cite triggers;
-   reusable operational values;
-   platform-specific behavior already provided by a supported
    component.

Prefer editable configuration, skills, or reusable components.

### 11.1 Environment Configuration Over Code Constants

When a value may reasonably differ between environments, deployments,
customers, workloads, or operational conditions, consider configuring it
through environment variables or editable configuration instead of
declaring the operational value directly in application code.

This applies especially to:

-   feature flags;
-   queue sizes and limits;
-   TTLs;
-   timeouts;
-   retry counts;
-   rate limits;
-   concurrency limits;
-   batch sizes;
-   memory/cache limits;
-   provider/model selection;
-   service URLs;
-   ports;
-   resource thresholds;
-   retention periods.

Before hardcoding an operational value, ask:

> Could an operator reasonably need to change this value between
> environments without changing application logic?

If yes, prefer environment/configuration.

If no, keep it as a source-level constant.

### 11.2 Do Not Externalize True Invariants

Do not create environment variables merely to avoid having a constant in
code.

Keep true implementation invariants in source code, such as:

-   protocol constants;
-   schema field names;
-   internal enum values;
-   serialization formats;
-   fixed security invariants;
-   algorithmic constants.

Security-critical invariants must remain enforced in code even when
related operational settings are configurable.

### 11.3 Configuration Requirements

When introducing an environment-configurable value:

1.  Use a clear, descriptive environment variable name.
2.  Validate type and range in code.
3.  Provide a safe default when appropriate.
4.  Document the variable and its purpose.
5.  Do not silently accept invalid configuration.
6.  Avoid duplicating the same configuration value across source files.
7.  Prefer the existing centralized configuration layer when available.
8.  Verify the configured value in the relevant test/deployment
    environment.

Use named constants for repeated values that are genuinely source-level
invariants.

------------------------------------------------------------------------

## 12. Reusable Architecture

Features should be designed as reusable components.

Prefer components that can:

-   be enabled/disabled;
-   be configured;
-   be independently tested;
-   be reused across projects;
-   fail independently;
-   scale independently.

Do not hardcode platform behavior when an appropriate third-party
component already provides the required capability.

Example:

``` text
Valkey → cache / session retention / queues / rate limiting
```

when appropriate to the architecture.

Before adding new infrastructure or application logic, consider whether
an existing component already provides the required capability.

------------------------------------------------------------------------

## 13. Reliability & Concurrency

Workflows should be asynchronous and non-blocking by default.

Use sequential execution only when:

-   ordering is required;
-   a data dependency exists;
-   transactional correctness requires it.

Avoid:

-   unnecessary blocking;
-   crash loops;
-   edge ports going down;
-   unbounded retries;
-   indefinite waits.

Router timeouts must be configurable and fault tolerant.

Free-model routers may require additional time for:

-   model switching;
-   retries;
-   provider failover;
-   availability discovery.

Use appropriate retry/grace periods while preventing indefinite hangs.

------------------------------------------------------------------------

## 14. Zalo Component Integrity

`ENABLE_ZALO=1` must start:

-   `zalo-proxy`;
-   `zalo-api`.

`zalo-api` provides channel administration such as:

-   allowlists;
-   `!zalo`;
-   sole-admin DM.

A logged-in bridge alone is insufficient.

Health checks and stack-watch must report failure when Zalo is enabled
but `zalo-api` is missing or unhealthy.

**Persistence:** Zalo admin, users, DMs, groups/threads (and deny list) are
stored in PostgreSQL via `zalo-api` (CRUD under `/v1/zalo/...`). Text files
such as `zalo_admin_users.txt` are migration/fallback only — never the
long-term source of truth on `main`.

**Branch language & test identity (lab vs production):**

-   **`develop` (lab only):** Inject / bridge simulation tests may use the
    lab Zalo identity **Tn** and Vietnamese user phrasing
    (`ZALO_TEST_USER_NAME=Tn`, Vietnamese greeting/schedule strings). Do not
    hardcode Tn’s numeric id or lab credentials in committed source.
-   **`main` (production-ready):** Must work for **any** sole admin account
    (no Tn-only assumption). Default product copy, SOUL, and operator-facing
    docs/messages prefer **English**; Vietnamese (and other languages) remain
    user-driven via reply-in-user-language rules — not lab identity.

------------------------------------------------------------------------

## 15. Source-First Fixes

When a lab/VPS problem is discovered:

``` text
Reproduce
   ↓
Diagnose
   ↓
Fix repository source
   ↓
Normal Git workflow
   ↓
Pull revision
   ↓
Rebuild/recreate affected services
   ↓
Verify
```

Never permanently fix a problem by:

-   hand-editing files on the VPS;
-   copying one-off patches or inventing `*.patch` / hotpatch files
    instead of updating the setup script that should have been correct;
-   shipping temporary scripts as the lasting fix;
-   modifying containers manually;
-   changing host configuration solely to hide a source bug.

When the bug is in install, first-setup, ensure-\*, lab-enable, or
`run.sh` wiring: **update that setup file/script**. A sidecar patch
that papers over a broken setup path is a Hard Gate violation.

Temporary probes under:

``` text
scripts/temp/
hermes/temp/
```

are allowed for diagnosis only and must remain gitignored.

------------------------------------------------------------------------

## 16. Lab Isolation

Committed source must contain no lab identity.

Never commit:

-   VPS IP addresses;
-   lab hostnames;
-   login names;
-   passwords;
-   API keys;
-   tokens;
-   production identifiers;
-   personal data.

Use environment variables such as:

``` text
ASSISTANT_SSH_*
```

and generic placeholders:

``` text
USER@HOST
```

Lab/test scripts belong in gitignored temporary directories.

Never place real host details in:

``` text
scripts/main/
test/scripts/
```

or other committed product paths.

------------------------------------------------------------------------

## 17. Deployment Safety

Do not:

-   deploy to the VPS without explicit permission;
-   push changes without explicit permission;
-   create a merge request without explicit permission.

**Always ask the user** before opening or merging any GitHub/GitLab
merge request. A prior conversation where the user once said “create
MR” does not authorize later MRs — ask again for each new change set.

Before implementing a new requirement:

1.  Switch to `develop`.
2.  Create the appropriate `feature/*` or `fix/*` branch.
3.  Implement and test.
4.  Follow [`docs/GIT.md`](./docs/GIT.md) for merge workflow.

Do not merge directly into protected branches.

------------------------------------------------------------------------

## 18. Remote Operations

When operating against a remote host:

-   avoid CRLF in shell commands;
-   prefer single-line SSH commands when appropriate;
-   fail immediately on non-zero exit codes;
-   handle PowerShell escaping correctly;
-   preserve UTF-8;
-   prefer `scripts/main/Update-StackRemote.ps1` for approved remote
    synchronization.

Never send scripts to the VPS for testing without explicit permission.

### 18.1 Monitor while patching

When patching the Zalo bridge, Hermes plugin, host units, or related
services on a lab/host:

1.  Keep abnormal-log streams open (or re-check immediately after the
    patch) for at least one heal/restart cycle:
    -   Hermes: `docker logs -f assistant-hermes-1 2>&1` (use the live
        Hermes container name if it differs).
    -   Zalo bridge: `journalctl --user -u com.hermes.zaloplugin -f`
2.  Watch for `EADDRINUSE`, repeated exit/restart storms, `media-proxy`
    / `/media/fetch` 404s, SSE drop (`sseClients=0` while logged in),
    and unexpected `ERROR` / exception spam.
3.  If a crash-loop or abnormal log appears, stop and fix the root cause
    in repository source — do not leave an orphan listener competing
    with the systemd unit. Reference:
    [`scripts/HISTORY.md`](./scripts/HISTORY.md)
    **2026-08-21 11:20 +07 — Bridge crash-loop on :8787; Hermes cannot
    POST /media/fetch**.

------------------------------------------------------------------------

## 19. Test Configuration Cleanup

After testing:

1.  Restore original/default configuration.
2.  Remove test-only flags.
3.  Remove temporary environment variables.
4.  Remove temporary files.
5.  Verify no test-specific source/configuration remains.
6.  Run a final repository/status check.
7.  **Monitor for post-test crash-loops.** Test cases and heal scripts
    may leave the Zalo bridge or other services restarting. Before
    declaring the run finished, inspect abnormal logs:
    -   `docker logs -f assistant-hermes-1 2>&1`
    -   `journalctl --user -u com.hermes.zaloplugin -f`
    Confirm the bridge unit is `active` (not `auto-restart`), Hermes is
    not spamming media-proxy / SSE errors, and unrelated workers are not
    flapping. See
    [`scripts/HISTORY.md`](./scripts/HISTORY.md)
    **2026-08-21 11:20 +07 — Bridge crash-loop on :8787**.

A test is not complete until the environment is restored **and** no
new crash-loop or abnormal log storm remains.

------------------------------------------------------------------------

## 20. Verification Before Completion

Never report a task as complete merely because a command succeeded.

Before finishing:

1.  Verify the changed behavior.
2.  Run relevant tests.
3.  Run regression tests for affected functionality.
4.  Check for unintended changes.
5.  Check repository status.
6.  Verify temporary files/configuration are removed.
7.  Verify services are healthy.
8.  Verify architecture boundaries remain intact.
9.  Update the changelog when required.
10. Re-check Hermes and Zalo bridge logs for crash-loops or abnormal
    spam after any patch or test (§18.1 / §19).

For installation/deployment tasks, verify all services.

Hermes must connect to:

-   **OmniRouter** by default;
-   **9Router** when that optional component is enabled.

------------------------------------------------------------------------

## 21. Change History

Every meaningful change must be recorded with a timestamp in:

``` text
docs/CHANGELOG.md
```

History should describe:

-   what changed;
-   why it changed;
-   affected components;
-   important compatibility implications;
-   test/verification status.

------------------------------------------------------------------------

## 22. Documentation

Documentation must be written in English and remain human-readable.

For architecture-related changes, document:

-   component responsibilities;
-   data flow;
-   data stores;
-   short-term memory;
-   long-term memory;
-   when data moves between stores;
-   retention behavior;
-   configuration;
-   failure behavior;
-   operational requirements.

------------------------------------------------------------------------

## 23. Knowledge Retrieval

Knowledge list/find/cite operations should return the top 5 results and
report how many additional results remain.

Do not expose unnecessary result volume.

------------------------------------------------------------------------

## 24. Safe Refactoring

Before moving, deleting, or renaming code:

1.  Search for all references.
2.  Verify runtime imports/symbols.
3.  Check configuration references.
4.  Check tests.
5.  Check skills/plugins.
6.  Check documentation.
7.  Only then modify or remove the code.

Never remove a component merely because it appears unused from a single
search result.

------------------------------------------------------------------------

## 25. Anti-Regression Rule

A fix must not knowingly regress unrelated functionality.

Before completing a change, consider:

-   dependent components;
-   concurrency behavior;
-   error handling;
-   fallback behavior;
-   security boundaries;
-   API compatibility;
-   existing integrations;
-   existing tests.

If a regression is discovered, fix the underlying interaction rather
than weakening the regression test.

------------------------------------------------------------------------

## 26. Completion Standard

A task is **NOT complete** when:

``` text
the current error disappears
```

It is complete only when:

``` text
failure reproduced
    ↓
root cause identified
    ↓
root cause fixed in source
    ↓
regression test added/updated
    ↓
variant tested
    ↓
affected tests pass
    ↓
no workaround remains
    ↓
no temporary state remains
    ↓
architecture remains valid
    ↓
verification completed
```

**Never optimize for "green now." Optimize for "correct and remains
correct."**

------------------------------------------------------------------------

## 27. Agent Decision Rule

Before making a change, ask:

1.  What is the actual requirement?
2.  What is the current architecture?
3.  What is the root cause?
4.  Is there already a skill/component/configuration for this?
5.  Could an environment variable or editable configuration be more
    appropriate than a code constant?
6.  Will this change generalize beyond the current input?
7.  Could this change bypass a test, validation, integration, or
    security boundary?
8.  How will recurrence be tested?
9.  What unrelated behavior could regress?
10. Can the change be reverted cleanly?
11. What evidence proves the task is actually complete?

If the answer to the root-cause or verification questions is unknown,
**do not declare the task complete**.

------------------------------------------------------------------------

## 28. Existing Lab Cases

Existing lab cases:

[`test/cases/`](./test/cases/)

Procedure:

[`test/RULES.md`](./test/RULES.md)

Cases not to run:

  -------------------------------------------------------------------------------
  Case                                File
  ----------------------------------- -------------------------------------------
  Skills mount + auto-learn           `test/cases/12-skills-auto-learn.md`

  Exact text poster                   `test/cases/13-image-text-poster.md`

  Internal docs knowledge-first       `test/cases/14-knowledge-internal-rag.md`
  -------------------------------------------------------------------------------

------------------------------------------------------------------------

## 29. Required Test Cases

When required by the requirement, use the applicable cases under:

``` text
test/cases/
```

Do not run unrelated expensive test suites merely for the appearance of
verification.

### 29.1 “Run all test cases” means §15 Case index (full)

When the operator asks to run **all test cases**, **all tests**, or the full
lab suite, run the **entire** [`test/RULES.md`](./test/RULES.md) **§15 Case index**:

1.  Every **unit script** listed under §15 (offline batch).
2.  Every **lab/VPS script** listed under §15 (SSH; real Zalo traffic where
    applicable — Tn on develop lab, any sole admin on `main`).
3.  Do **not** substitute a smaller subset (e.g. health + preflight only)
    unless the operator explicitly scopes the run.

Batch runner: `test/scripts/run_case_index_lab.py` (keep in sync when §15
grows). Gap cases **40–74** are separate unless the operator asks for them.

After **all** rounds finish, **before stopping the host**, run post-lab restore
(§19.1) — not optional when the operator requested a full lab.

### 29.2 Post-lab restore (after all test rounds)

After the **final** lab round, before stopping the VPS or declaring complete:

1.  `bash scripts/main/post-lab-restore.sh` — Omni OpenCode combos, Zalo
    session, health matrix, router chat smoke.
2.  Confirm connectivity: bridge `loggedIn` + `sseClients≥1`, zalo-api,
    model-router, Hermes (no crash-loop in recent logs).
3.  Do **not** leave empty `hermes`/`classifier` combos — that breaks
    manual Zalo chat (configuration gap, not a bridge bug). See
    [`test/RULES.md`](./test/RULES.md) § Post-lab restore.

------------------------------------------------------------------------

## 30. Editable Companions

  ---------------------------------------------------------------------------
  Path                                    Purpose
  --------------------------------------- -----------------------------------
  `docs/GIT.md`                           Branch / MR workflow

  `docs/CHANGELOG.md`                     Timestamped change history

  `test/RULES.md`                         Lab/deployment/test procedure

  `hermes/main/messages/`                 Admin-editable user-facing strings

  `config/agent/bad-words.txt`            Scrubbed words/phrases

  `scripts/main/Update-StackRemote.ps1`   Approved remote synchronization
                                          helper
  ---------------------------------------------------------------------------

------------------------------------------------------------------------

## 31. Final Agent Checklist

Before declaring any task complete:

-   [ ] Requirement is understood.
-   [ ] Current architecture was inspected.
-   [ ] Existing skills/components/configuration were checked.
-   [ ] Root cause was identified when fixing a problem.
-   [ ] No symptom-only workaround was introduced.
-   [ ] Operational values were considered for
    environment/configuration.
-   [ ] True invariants remain enforced in source.
-   [ ] Tests represent the current architecture.
-   [ ] Tests were not weakened to obtain a pass.
-   [ ] Real integrations were used when required and available.
-   [ ] Regression coverage was added or updated.
-   [ ] A meaningful failure variant was tested when practical.
-   [ ] Relevant tests passed.
-   [ ] No temporary test configuration remains.
-   [ ] No temporary files remain.
-   [ ] No lab credentials or host identity entered committed source.
-   [ ] No unauthorized push/MR/deployment was performed.
-   [ ] Services were verified when applicable.
-   [ ] Post-test / post-patch logs checked for bridge or service
    crash-loops (`docker logs` Hermes; `journalctl --user` Zalo
    plugin) — see HISTORY **2026-08-21 11:20 +07**.
-   [ ] Documentation was updated when required.
-   [ ] `docs/CHANGELOG.md` was updated when required.
-   [ ] Repository status was checked.
-   [ ] Completion is based on evidence, not merely a successful
    command.

**Final principle:**

> **Do not optimize for making the current failure disappear. Optimize
> for fixing the underlying system so the same class of failure does not
> return.**
