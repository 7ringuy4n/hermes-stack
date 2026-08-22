# scripts/

**Default: `main/`** — `run.sh` and product docs always call `scripts/main/…`.

| Folder / file | Purpose | Git |
|---|---|---|
| [`main/`](./main/) | **Default** product ops (Docker, first-setup, checks) | **commit** |
| [`temp/`](./temp/) | One-off deploy/probe/hotfix (host-specific) | **ignored** |
| [`HISTORY.md`](./HISTORY.md) | Timestamped **issues + root causes + fixes** (ops companion to `docs/CHANGELOG.md`) | **commit** |

```bash
# product (default paths)
sudo bash scripts/main/install-docker.sh
bash run.sh first-setup-llm
bash run.sh update
bash run.sh check-media
bash run.sh check-security
bash run.sh first-setup-openbao
bash run.sh post-ready-learn

# local-only
python scripts/temp/probe-low-status.py
```

Same default-`main` / local-`temp` split: [`hermes/`](../hermes/README.md).

## Lab notes

- Qwen lab performance: [docs/QWEN_PERFORMANCE.md](../docs/QWEN_PERFORMANCE.md)
- Ops history: [HISTORY.md](./HISTORY.md)
