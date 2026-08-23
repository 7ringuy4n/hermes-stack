# Assistant stack notes (ComfyUI)

Official Hermes skill: this folder’s `SKILL.md` (from NousResearch/hermes-agent `skills/creative/comfyui`).

## This deploy

Prefer **dispatcher** image gen first:

```bash
curl -sS -X POST http://dispatcher:8090/v1/image \
  -H 'content-type: application/json' \
  -d '{"prompt":"<text>"}'
```

Fallback order (Medium+): `comfy-cpu` → `comfy-gpu` → `omni` (OmniRouter when Comfy fails).

| Env | Meaning |
|---|---|
| `COMFYUI_CPU_URL` | default `http://comfyui-cpu:8188` |
| `COMFYUI_GPU_URL` | default `http://comfyui-gpu:8188` |
| `COMFYUI_HAS_GPU` | `1` enables GPU FLUX.2 klein path |
| `COMFYUI_CPU_WORKFLOW` | `sdxl` or `sd15` |

Checkpoints: `/data/assistant/comfyui/models/checkpoints`.

Use the full `SKILL.md` + scripts only when you need custom workflows beyond `/v1/image`.
