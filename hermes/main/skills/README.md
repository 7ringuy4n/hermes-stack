# hermes / main / skills

**Default** mount (`./hermes/main/skills` → `/opt/data/skills`).

## Layout

| Area | Path | Notes |
|---|---|---|
| **Core** | `core/*` | Answering, reasoning, verification, safety, … |
| **Knowledge** | `knowledge/*` | Research, web strategy, RAG, documents |
| **Coding** | `coding/*` + `coding/SKILL.md` router | Debug, review, security, git, testing |
| **Communication** | `communication/*` | Email, chat tone, translation, **friendly-response** (default), **vi-people-terms** (Vietnamese people/gender) |
| **Documents** | `file-gen` / `documents` (create+send via Dispatcher); advanced local `*-tools-local` only | |
| **Web** | `web-search`, `searxng*`, `tavily`, `firecrawl` | OmniRouter → SearXNG |
| **Core routing** | `core/worker-routing` | Classifier JSON → skill → worker table |
| **Schedule** | `schedule` | Go schedule worker (SQLite). Hermes does not tick cron. |
| **Media/file** | `media-file`, `image-gen`, `media-out`, `comfyui`, `file-gen` | Worker owns OCR/ComfyUI |
| **Security** | `security` | AV/YARA/sandbox/judge worker; not a classify `task_hint` |
| **Vendor** | `vendor/*` | Upstream packs + `ATTRIBUTION.md` / licenses |

Sources and priority: plan doc `hermes plan/docs/hermes_skill_sources.txt` (P0 fetched: Anthropic skill-creator, obra superpowers, Trail of Bits audit plugins).

## Promote from temp

Old stack skills under `hermes/temp/skills` (gitignored):

```bash
cp -a hermes/temp/skills/<name> hermes/main/skills/<name>
```

Skill fetch clones: `hermes/temp/skill-fetch/` (gitignored).

## Related

- [vendor/CATALOG.md](./vendor/CATALOG.md)
- [temp/skills](../../temp/skills/README.md)
