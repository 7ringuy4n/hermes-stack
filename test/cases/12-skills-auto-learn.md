# Case: skills mount + post-ready auto-learn (Media|File worker)

Hermes loads skills from the compose bind mount; **post-ready-learn** mirrors markdown into `$ASSISTANT_DATA_DIR/docs/` and runs ingest `learn/scan` (auto when `LEARN_REQUIRE_APPROVE=0`).

## Goal

- After destroy + Medium redeploy from source, new skill folders exist under `/opt/data/skills` in Hermes.
- `bash run.sh post-ready-learn` (or `up`) indexes skill markdown into Qdrant `knowledge_chunks`.
- Ingest catalog lists skill-derived documents (top 5 + total count).

## Preconditions

- `WORKER_MEDIA_FILE=active`.
- Ingest + embedding + model-router healthy.
- `hermes/main/skills` contains real skills (not only `_example`).

## Steps

1. **Clean:** backup+verify, then destroy stack; remove mirrored docs under `$ASSISTANT_DATA_DIR/docs/skills` (optional full `docs/` refresh).
2. **Deploy:** sync source tree; ensure `WORKER_MEDIA_FILE=active`; `bash run.sh up` (rebuild dispatcher if image-gen changed).
3. **Learn:** confirm `post-ready-learn` OK (or run `bash run.sh post-ready-learn`).
4. **Mount check:** Hermes container has category skills, e.g. `core/answering/SKILL.md`, `image-gen/SKILL.md`, `communication/friendly-response/SKILL.md`, `communication/vi-people-terms/SKILL.md`.
5. **Catalog:** `GET /v1/learn/list?q=image-gen&limit=5` — expect ≥1 hit; report total `count`.
6. **Find:** `POST /v1/learn/find` with selector `knowledge-rag` or `skills` — chunk hits or document names present.
7. **Router path:** `curl` model-router health after deploy.

## Pass criteria

- post-ready-learn exits 0; `learn/scan` reports `scanned>0` and `auto_ingest=true` (when approve off).
- Hermes bind mount lists new skill paths.
- learn/list returns skill-related titles for at least one wrapper skill (`image-gen`, `knowledge-rag`, `core/answering`).
- model-router health OK.
- Reports contain no hostnames, IPs, or account names.

## Fail events

- Empty skills dir → post-ready-learn skips (record SKIP).
- Ingest down during learn → non-zero exit; stack must not crash-loop Hermes.

## Fixtures

- Run A: full destroy + Media|File worker + post-ready-learn after P0 skill import.
- Run B: `post-ready-learn` only (no destroy) after skill edit — catalog count increases or refreshes.
