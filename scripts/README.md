# scripts/

**Default: `main/`** — `run.sh` and product docs always call `scripts/main/…`.

| Folder | Purpose | Git |
|---|---|---|
| [`main/`](./main/) | **Default** product ops (Docker, first-setup, checks) | **commit** |
| [`temp/`](./temp/) | One-off deploy/probe/hotfix (host-specific) | **ignored** |

```bash
# product (default paths)
sudo bash scripts/main/install-docker.sh
bash run.sh first-setup-llm
bash run.sh update
bash run.sh check-medium
bash run.sh check-high
bash run.sh first-setup-openbao
bash run.sh post-ready-learn

# local-only
python scripts/temp/probe-low-status.py
```

Same default-`main` / local-`temp` split: [`hermes/`](../hermes/README.md).
