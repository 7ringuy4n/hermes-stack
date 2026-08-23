# scripts/

**Default: `main/`** — `run.sh` and product docs always call `scripts/main/…`.

| Folder / file | Purpose | Git |
|---|---|---|
| [`main/`](./main/) | **Default** product ops (Docker, first-setup, checks) | **commit** |
| [`temp/`](./temp/) | Local helpers / one-off probes (host-specific). Keep `generate_env_secrets.py` | **ignored** (except documented helper) |
| [`HISTORY.md`](./HISTORY.md) | Timestamped **issues + root causes + fixes** (ops companion to `docs/CHANGELOG.md`) | **commit** |

```bash
# product (default paths)
sudo bash scripts/main/install-docker.sh
bash run.sh first-setup-omnirouter
bash run.sh update
bash run.sh check-media
bash run.sh check-security
bash run.sh first-setup-openbao
bash run.sh post-ready-learn

# local helper (optional)
python3 scripts/temp/generate_env_secrets.py --out .env --force
```

Same default-`main` / local-`temp` split: [`hermes/`](../hermes/README.md).

## Lab notes

- Qwen lab performance: [docs/QWEN_PERFORMANCE.md](../docs/QWEN_PERFORMANCE.md)
- Ops history: [HISTORY.md](./HISTORY.md)
- Workers: [docs/00-workers.md](../docs/00-workers.md)
