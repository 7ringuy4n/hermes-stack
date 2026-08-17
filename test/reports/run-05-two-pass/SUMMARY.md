# Lab two-pass SUMMARY — run-05 (sanitized)

No hostnames, IPs, or account names.

- Run ID: **run-05-two-pass**
- Profile: **High** + Zalo + edge (Traefik local, API Gateway)
- Started: 2026-08-17 ~14:55 +07
- Finished: 2026-08-17 ~15:16 +07

<table>
  <thead>
    <tr>
      <th>Pass</th>
      <th>Mode</th>
      <th>Deploy</th>
      <th>Zalo text</th>
      <th>Zalo text+media</th>
      <th>Isolation</th>
      <th>Profile switch</th>
      <th>Final</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>1</td><td>local</td><td>PASS</td><td>PASS (N≤24)</td><td>PASS* (fail @ N=8)</td><td>PASS</td><td>PASS after notify fix</td><td>PASS</td></tr>
    <tr><td>2</td><td>local</td><td>PASS (Quick start)</td><td>n/a</td><td>WARN (N=2 ok; N=4 text timeout)</td><td>PASS</td><td>PASS (dry-run)</td><td>PASS</td></tr>
  </tbody>
</table>

\* Mixed-media fail event is required: last all-success **N=4**, first-fail **N=8** (text HTTP 503; one image 502). Image delay stayed ~0.3–6s.

## Pass 1 — sync source + deploy + fix on error

| Step | Result | Notes |
|------|--------|-------|
| Sync + High/Zalo `run.sh up` | PASS | Hermes×2, Traefik, Gateway, zalo-api, SSE=1 |
| Isolation risks (10) | PASS | sandbox/judge/AV off; no sock; EICAR→RISK via YARA |
| Profile switch (11) | PASS after fix | High↔Medium; Zalo kept; bogus tier/flag RC=2 |
| Add `ENABLE_NOTIFY=1` | PASS | notify + alert-watch up |
| Remove `ENABLE_NOTIFY=0` | FAIL then FIXED | Compose `--remove-orphans` left notify running |
| Downgrade High→Medium | PASS | OpenBao/authz gone; OCR + Zalo still up |
| Upgrade Medium→High | PASS | OpenBao/authz/security-manager back; Hermes×2 |
| Zalo text concurrent (08) | PASS | N=4→24 all ok; SSE=1 |
| Zalo text+media (09) | PASS (fail-event) | See delay table |

### Source fixes during pass 1

- `run.sh`: after `up`/`update`, drop containers for **disabled** compose profiles (notify, AV, sandbox, monitor, CloudDrive). Compose does not treat them as orphans.
- `first-setup-9router-hermes.py`: remove leftover `hexprefix_*hermes*` names. **Do not** `--remove-orphans` on the LLM-only compose set (that omitted edge YAML and dropped Traefik).

### Profile switch (existing / add / remove)

| Check | Result |
|-------|--------|
| Existing `ENABLE_ZALO=1` through cycle | PASS |
| Archive `profile-options.env` + `env.sealed` | PASS |
| Add notify | PASS |
| Remove notify (after `do_stop_disabled_optionals`) | PASS |
| High→Medium drops OpenBao/authz | PASS |
| Medium→High restores High overlay + Hermes×2 | PASS |
| Fail: `switch-profile bogus` / unknown flag | PASS (RC=2) |

### Zalo concurrent text (`cases/08`)

Last all-success N: **24**. First-fail: none ≤24. SSE=1.

### Zalo concurrent text + media (`cases/09`) — delay

| N | ok | fail | text p50 / p95 / max ms | image p50 / p95 / max ms |
|---|----|------|-------------------------|--------------------------|
| 2 | 2 | 0 | 8485 / 8485 / 8485 | 379 / 379 / 379 |
| 4 | 4 | 0 | 3699 / 15668 / 15668 | 323 / 331 / 331 |
| 8 | 3 | 5 | 36 / 40 / 40 (503s) | 2106 / 6546 / 6546 |

- Last all-success N: **4**
- First-fail N: **8** (text **503**, one image **502**)
- SSE after N=8: **0** (watch restored by pass 2 up)

## Pass 2 — script-only Quick start (no source edits)

| Step | Result | Notes |
|------|--------|-------|
| `run.sh down` + `up` + `first-setup-llm` | PASS | README Quick start |
| Traefik `/health` | PASS | |
| Gateway `/health` | PASS | |
| Zalo | PASS | loggedIn, sseClients=1 |
| Isolation risks | PASS | 0 fail |
| Profile dry-run | PASS | no `.env` write |
| Mixed media N≤4 | WARN | N=2 all ok; N=4 one text **60s timeout**; SSE=1 |

Pass 2 mixed delay: text p50 ~5.4s (N=2), ~10.6s / 60s (N=4); image ~0.3–1.4s.

## Left running

High + Zalo + edge, isolation defaults off, notify off.
