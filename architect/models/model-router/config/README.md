# Model-router config — bake fallbacks only

**Do not edit JSON in this folder as the source of truth.**

| Bake file | Hermes skill SoT |
|-----------|------------------|
| `classify.json` | [`hermes/main/skills/classify/`](../../../../hermes/main/skills/classify/) (envelope + `parts/`; bake is assembled `system`) |
| `outbound.json` | [`hermes/main/skills/outbound/outbound.json`](../../../../hermes/main/skills/outbound/outbound.json) |
| `web-search-combo.json` | [`hermes/main/skills/web-search/web-search-combo.json`](../../../../hermes/main/skills/web-search/web-search-combo.json) |

Sync:

```bash
bash scripts/main/sync-model-router-skills.sh
```

Runtime (`router-worker`) mounts `./hermes/main/skills` → `/opt/data/skills` and assembles classify parts at load. Bake `classify.json` is self-contained for image COPY.

`heuristic.json` was removed — never loaded; keyword lists are not classify SoT.
