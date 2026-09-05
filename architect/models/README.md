# Models layer

## Boundary

| Owns | Does not own |
|---|---|
| model-router request normalization/routing | Hermes skill policy/prompt content |
| OmniRoute lifecycle and attribution integration | Operator provider credentials/membership decisions |
| dispatcher and asynchronous jobs | Persistent conversation/knowledge data |

```text
Hermes/workers → model-router → OmniRoute priority combo → provider
                         └────→ dispatcher/jobs when a tool workflow needs it
```

`omni-attribution/` fills missing stack-owned attribution for non-chat
OmniRoute calls. It does not mutate providers, combos, order, or strategy.

## Packages

| Package | Function |
|---|---|
| [model-router/](./model-router/README.md) | OpenAI-compatible internal proxy, classify endpoint, task/correlation metadata |
| [omni-router/](./omni-router/README.md) | OmniRoute deployment/integration (directory name retained for compatibility) |
| [omni-attribution/](./omni-attribution/README.md) | Requested-combo attribution completion |
| [dispatcher/](./dispatcher/README.md) | Search/media/job helpers; not an LLM provider router |

## Capability aliases

`hermes`, `classifier`, `web-search`, `image-gen`, `vision-ocr`, `embedding`,
and `image-edit` are OmniRoute combo names, not vendor model IDs. Setup ensures
required shells/metadata while preserving operator-managed members.

SearXNG is a sibling media-worker service. There is no 9Router, second
OmniRouter, local OCR engine, ComfyUI, video-gen, or video-edit runtime.

See [docs/06-model-routing.md](../../docs/06-model-routing.md).
