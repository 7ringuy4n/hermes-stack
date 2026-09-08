# Case 76 — DM/group capability concurrency

Prove that independent conversations can execute real capabilities at the same
time without crossed replies, lost artifacts, duplicate delivery, or queue
residue. This complements quote-isolation tests; it does not replace them.

## Workloads

Run two separate bursts through the live bridge. Each burst contains exactly
two requests admitted at the same time: one authorized DM request and one
addressed request in the named three-member test group.

1. Current-weather burst: use different cities and unique source-message
   correlations. Both replies must contain the correct city and current
   conditions. OmniRoute must attribute at least two new search calls to combo
   `web-search`; this provider-side evidence is the search gate even when a
   model omits requested citation formatting.
2. File-generation burst: request one DOCX per conversation with distinct
   titles and exact marker text. Both acknowledged document deliveries must be
   correlated to their own source message. Extract each delivered package and
   verify its title and marker; a text-only claim that a file was created is a
   failure.

Resolve all identities from runtime configuration and durable channel state.
Verify the group has exactly three members and contains the designated test
user. Never write numeric identities into source or reports.

## Pass gate

- Both requests in each burst are accepted before waiting for results.
- Every source has exactly one acknowledged terminal result or document.
- DM output returns only to the DM and group output only to the group.
- Weather answers pass objective checks and model-based semantic evaluation.
- Both DOCX packages exist, open, and contain their distinct requested content.
- The two conversation queues drain fully and no Hermes replica logs a queue
  turn timeout during the observation window.
- Record per-request admission-to-delivery latency and total burst duration.

Run with:

```bash
python test/scripts/zalo_dm_group_capability_concurrency_lab.py
```

Repeat with one and two Hermes replicas when comparing capacity. Provider
latency must be reported separately from local queue behavior.
