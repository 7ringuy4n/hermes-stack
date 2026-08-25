# Model-router config — bake fallbacks only

**Do not edit JSON in this folder as the source of truth.**

| Bake file | Hermes skill SoT |
|-----------|------------------|
| `classify.json` | [`hermes/main/skills/classify/classify.json`](../../../../hermes/main/skills/classify/classify.json) |
| `outbound.json` | [`hermes/main/skills/outbound/outbound.json`](../../../../hermes/main/skills/outbound/outbound.json) |
| `web-search-combo.json` | [`hermes/main/skills/web-search/web-search-combo.json`](../../../../hermes/main/skills/web-search/web-search-combo.json) |

Sync:

```bash
bash scripts/main/sync-model-router-skills.sh
```

Runtime (`router-worker`) mounts `./hermes/main/skills` → `/opt/data/skills` and sets:

- `MODEL_ROUTER_CLASSIFY=/opt/data/skills/classify/classify.json`
- `MODEL_ROUTER_OUTBOUND=/opt/data/skills/outbound/outbound.json`
- `WEB_SEARCH_COMBO_PATH=/opt/data/skills/web-search/web-search-combo.json`

`heuristic.json` was removed — never loaded by code; keyword NLU belongs in classify LLM prompt, not substring lists.
