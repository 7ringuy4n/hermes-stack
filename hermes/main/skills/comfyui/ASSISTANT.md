# ComfyUI skill — disabled

This stack removed ComfyUI image/video generation.

Use:

- `image-gen` → dispatcher `/v1/image` + combo `image-gen`
- `video-gen` → policy refuse
- `multi-purpose` → hermes chat plan + image-gen / file-gen
