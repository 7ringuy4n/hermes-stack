# ComfyUI API workflows for dispatcher /v1/image

| File | Profile | Checkpoint env / default name |
|---|---|---|
| `sdxl.json` | CPU default (`COMFYUI_CPU_WORKFLOW=sdxl`) | `sd_xl_base_1.0.safetensors` |
| `sd15.json` | CPU alt (`COMFYUI_CPU_WORKFLOW=sd15`) | `v1-5-pruned-emaonly.safetensors` |
| `flux2_klein_4b.json` | GPU (`COMFYUI_HAS_GPU=1`) | `flux2-klein-4b.safetensors` |

Place matching checkpoints under the ComfyUI models volume (`/data/assistant/comfyui/models/checkpoints`).
Adjust `ckpt_name` in JSON if your filenames differ.

`{{PROMPT}}` is replaced by the dispatcher before submit.
