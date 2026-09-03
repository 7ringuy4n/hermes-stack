# 2026-08-28

3 incident(s). Times are UTC+7.

## 18:30 — Host regex scrub for chat/thread ids and locale folder text

### Symptom

Outbound sanitization used host regex (including locale-hardcoded folder wording) to hide chat/thread identifiers, conflicting with LLM-owned NLU/privacy rules.

### Root cause

Adapter post-filter tried to phrase-match identity leaks instead of classifying/outbound LLM policy.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Drop identity/DM/folder regex from adapter redact. Harden classify + outbound prompts; outbound may return cleaned `text` on send. Normalize outbound actions via a map.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never reintroduce host phrase regex for chat privacy. Keep path/secret structural redact only; privacy language belongs in classify/outbound SoT.

## 18:50 — Omni Grafana quota all zeros with scrape OK

### Symptom

OmniRouter LLM quota / usage panels showed 0 requests/tokens/cost and “No data” rate charts while OmniRouter scrape stayed OK.

### Root cause

`omni-exporter` (nine-exporter image) scraped legacy `/api/usage/stats` (and siblings). Current OmniRoute returns 404 there; optional 404 became empty usage while providers/login still succeeded, so scrape_success stayed 1.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Scrape `/api/usage/history` then `/api/usage/analytics`, coerce summary + list/dict breakdowns into the flat totals Grafana already queries. Keep older paths for 9Router compatibility.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

When OmniRoute renames usage APIs, update exporter path list and coercion — do not treat scrape_success alone as proof that usage series are populated.

## 19:30 — Excel with sheet soft-probe returned a new txt file

### Symptom

Reading an `.xlsx` that contained a soft env/secret probe in one sheet returned a newly created `.txt` instead of a host extract ack.

### Root cause

After ingest extract, office media paths were cleared but host-ack only ran for bare/blank office. Meaningful extracts could fall through to the classify→office_shortcut path, which treated sheet text as a create-file job.

### AI decision

Backfilled from legacy log. At fix time: prioritize durable core change over VPS hotpatch; align classify/skills when intent routing was involved.

### Fix (core)

Always host-ack office/text/ocr attachment reads (same as archives). Skip attachment-body secret classify for office (sheet cells are DATA; caption-only). Do not run office shortcuts on `[Attachment text —` payloads. Harden classify accordingly.

### Todo list

- Reproduce
- Fix core
- Regression test
- Verify on lab/VPS

### Prevent recurrence

Never route inbound office extracts into create-file shortcuts. Keep standalone short risk `.txt` refuse on the text kind path.
