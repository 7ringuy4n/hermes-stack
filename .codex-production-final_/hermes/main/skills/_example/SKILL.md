---
name: example-skill
description: "EXAMPLE TEMPLATE — copy this folder to create a new Hermes skill. Not routed in production (name starts with example)."
---

# Example skill (template)

Use this file as the pattern for every new skill under `hermes/main/skills/`.  
It mirrors the style of `common-rules` and `knowledge-learn` from the current skill set.

## When this skill runs

Describe **triggers** in the YAML `description` (Hermes uses it for routing) and optionally list phrases here:

- Example phrases: `example mode`, `demo skill`
- Hard gates (war/politics) still go to `content-policy` first via `mode-router`

## Must follow

1. Apply **`common-rules`**: one short message, Vietnamese if user is Vietnamese, no server paths, no progress spam.
2. Prefer **architect HTTP APIs** over inventing data.
3. Fixed user strings → `hermes/main/messages/*.json` when operators will edit them often.
4. Knowledge answers: **top 5** + rest count; empty → “no information”; **no guessing**; **no internet** on Low.

## Steps (example: knowledge-style lookup)

```bash
# 1) List / search local knowledge only
curl -sS "${INGEST_URL:-http://ingest:8099}/v1/learn/list?q=<keyword>&limit=${LEARN_LIST_LIMIT:-5}"

# 2) If documents empty → one line from hermes/main/messages/ux.json cite.empty
# 3) Else show up to 5 titles + "{n} more."
# 4) If ingest down → cite.ingest_down — do not dump chat memory
```

## Steps (example: remember a fact)

```bash
curl -sS "${MEMORY_URL:-http://memory:8095}/v1/remember" \
  -H 'content-type: application/json' \
  -d '{"text":"<durable fact>","kind":"semantic"}'
```

Do **not** tell the user “memory saved” unless they asked.

## Do not

- Hardcode secret/path probes here if a dedicated skill + message file can own them  
- Call web search on Low for manual/spec questions  
- Create new skills from chat automatically or announce “Skill created”

## Copy checklist

- [ ] Rename folder `_example` → `my-skill` (drop leading underscore if you want it live)
- [ ] Set unique `name` and routing `description`
- [ ] Link any new message keys in `hermes/main/messages/`
- [ ] Mention the skill in `mode-router` if it needs a hard case
