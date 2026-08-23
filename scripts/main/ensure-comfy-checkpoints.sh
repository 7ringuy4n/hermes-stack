#!/usr/bin/env bash
# Ensure ComfyUI has at least one SDXL checkpoint (empty dir => /v1/image 400/502).
# yanwk/comfyui-boot mounts ${DATA}/comfyui → /root, so real path is ComfyUI/models/checkpoints.
set -euo pipefail
DATA="${ASSISTANT_DATA_DIR:-${HERMES_DATA_DIR:-/data/assistant}}"
CKPT_DIR="${COMFYUI_CKPT_DIR:-$DATA/comfyui/ComfyUI/models/checkpoints}"
# Legacy wrong path (pre-fix); still honor files already dropped there.
LEGACY_CKPT_DIR="${COMFYUI_LEGACY_CKPT_DIR:-$DATA/comfyui/models/checkpoints}"
NAME="${COMFYUI_DEFAULT_CKPT:-sd_xl_base_1.0.safetensors}"
URL="${COMFYUI_DEFAULT_CKPT_URL:-https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors}"

mkdir -p "$CKPT_DIR"
shopt -s nullglob
existing=("$CKPT_DIR"/*.safetensors "$CKPT_DIR"/*.ckpt)
if ((${#existing[@]} == 0)); then
  existing=("$LEGACY_CKPT_DIR"/*.safetensors "$LEGACY_CKPT_DIR"/*.ckpt)
  if ((${#existing[@]} > 0)); then
    echo "ensure-comfy-checkpoints: found ${#existing[@]} file(s) in legacy $LEGACY_CKPT_DIR — copying into $CKPT_DIR"
    cp -n "${existing[@]}" "$CKPT_DIR/" || true
    existing=("$CKPT_DIR"/*.safetensors "$CKPT_DIR"/*.ckpt)
  fi
fi
if ((${#existing[@]} > 0)); then
  echo "ensure-comfy-checkpoints: ok (${#existing[@]} file(s) in $CKPT_DIR)"
  exit 0
fi

if [[ "${COMFYUI_AUTO_DOWNLOAD_CKPT:-1}" != "1" ]]; then
  echo "ensure-comfy-checkpoints: FAIL empty $CKPT_DIR (place $NAME or set COMFYUI_AUTO_DOWNLOAD_CKPT=1)" >&2
  exit 1
fi

dest="$CKPT_DIR/$NAME"
echo "ensure-comfy-checkpoints: downloading $NAME → $dest"
tmp="$dest.partial"
if command -v curl >/dev/null 2>&1; then
  curl -fL --retry 3 -o "$tmp" "$URL"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$tmp" "$URL"
else
  echo "ensure-comfy-checkpoints: need curl or wget" >&2
  exit 1
fi
mv -f "$tmp" "$dest"
echo "ensure-comfy-checkpoints: wrote $dest"
