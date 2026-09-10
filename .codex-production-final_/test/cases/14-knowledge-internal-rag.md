# Case: confidential / internal docs — knowledge-first (no open web)

Skills under `knowledge/` require local `knowledge_chunks` retrieval for internal technical documentation; no guessing; no open-web fallback.

## Goal

- Skill files exist on Hermes mount: `knowledge/knowledge-rag`, `knowledge/web-search`, `knowledge/research`.
- After case 12, ingest catalog can find `knowledge-rag` / `internal` / `confidential` wording from mirrored SKILL.md.
- Automated probe: learn/list or learn/find returns documents whose names/preview mention knowledge-rag or confidential/internal rules.

## Preconditions

- Case 12 PASS (skills learned).
- Medium+ ingest healthy.

## Steps

1. Verify mount:

```bash
docker exec hermes test -f /opt/data/skills/knowledge/knowledge-rag/SKILL.md
docker exec hermes test -f /opt/data/skills/knowledge/web-search/SKILL.md
```

2. Catalog probe:

```bash
curl -sS "http://127.0.0.1:8099/v1/learn/list?q=knowledge-rag&limit=5"
curl -sS -X POST "http://127.0.0.1:8099/v1/learn/find" \
  -H 'content-type: application/json' \
  -d '{"selector":"confidential"}'
```

3. Report top 5 titles + total `count` (RULE: top 5 + remainder count).

4. **Behavioral note (manual/chat):** queries framed as internal docs / software docs should route to knowledge-rag policy — record PASS if skill text is indexed; chat routing is optional manual spot-check.

## Pass criteria

- All three knowledge wrapper skills present on mount.
- learn/list or find returns ≥1 hit for `knowledge-rag` or `knowledge` after auto-learn.
- Reports contain no hostnames, IPs, or account names.

## Fail events

- Ingest empty for `knowledge-rag` after successful case 12 → FAIL (learn pipeline broken).
- web-search skill missing confidential/internal section on mount → FAIL.
