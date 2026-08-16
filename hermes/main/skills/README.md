# hermes / main / skills

**Default** mount (`./hermes/main/skills` → `/opt/data/skills`).

## What’s here (product)

| Group | Folders |
|---|---|
| Documents | `documents`, `markdown`, `pdf`, `docx`, `xlsx`, `file-gen`, `official/{pdf,docx,xlsx}` |
| Image | `image-gen`, `comfyui`, `official/comfyui` |
| Web | `tavily`, `firecrawl`, `searxng`, `searxng-search`, `vendor/tavily`, `vendor/firecrawl` |
| Coding / UI | `coding` (router), `vendor/mattpocock/*`, `vendor/ui-ux-pro-max/*` |
| Template | `_example` |

These are **new downloads** and/or the doc/web/comfy set you asked to keep in `main`.

## Live-matched skills → `hermes/temp/skills`

Old stack skills that also exist under `assistant/hermes_backup/skills` (chat, research, mode-router, …) stay in **temp** (gitignored) until you promote them.

```bash
cp -a hermes/temp/skills/<name> hermes/main/skills/<name>
```

## Related

- [temp/skills](../../temp/skills/README.md)  
- [vendor/CATALOG.md](./vendor/CATALOG.md)
