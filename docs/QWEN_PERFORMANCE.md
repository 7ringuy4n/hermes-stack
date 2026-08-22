# Qwen performance & concurrency sizing

Operator-facing guide for **Qwen as an optional OmniRouter component** and
recommended Zalo/workflow parallelism by host size.

Do not put hostnames, accounts, or secrets here.

Companions: [`CHANGELOG.md`](./CHANGELOG.md), [`../scripts/HISTORY.md`](../scripts/HISTORY.md).

## Component switch

| Knob | Default | Meaning |
|------|---------|---------|
| `ENABLE_QWEN` | `0` | Qwen inactive until operator turns it on |
| `QWEN_API_KEY` / `ALIBABA_API_KEY` / `DASHSCOPE_API_KEY` | empty | Optional cloud DashScope path when `ENABLE_QWEN=1` |
| `OLLAMA_BASE_URL` | empty | Host Ollama URL **as seen from Docker** (`http://host.docker.internal:11434`) |
| `OLLAMA_MODEL` | empty | Local Qwen chat id (e.g. `qwen2.5:7b` → combo member `ollama/qwen2.5:7b`) |
| `OMNIROUTER_COMBO_STRATEGY` | `round-robin` | Strategy for `hermes` / `classifier` |
| `hermes` / `classifier` members | **empty** | Filled when Qwen is active **and** cloud key or local Ollama is configured |
| `OMNIROUTER_QWEN_ONLY_PROVIDERS` | `1` | When Qwen active, deactivate non-Qwen LLM providers (skipped if `ENABLE_QWEN=0`) |
| `OMNIROUTER_QWEN_FAST_COMBO` | `qwen-fast` | Optional tiny (~1.5B/1.7B) combo; empty if catalog has none |
| `ZALO_WORKFLOW_PARALLEL` | **8** | Default parallel workflow jobs per turn (targets 5–10 concurrent multi-request users) |

When Qwen is **off**, first-setup still creates `hermes` + `classifier` as **empty** round-robin aliases (operator adds models in Omni Combos UI).

### Activate — cloud DashScope

```text
ENABLE_QWEN=1
QWEN_API_KEY=<dashscope-or-alibaba-key>
bash run.sh first-setup-omnirouter
```

### Activate — local Ollama (lab / CPU VPS, no cloud key)

```text
ENABLE_QWEN=1
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b
bash scripts/main/lab-enable-qwen-local.sh   # installs Ollama, pulls model, runs first-setup
```

Router Worker failovers to Ollama when Omni `hermes`/`classifier` return 503/400 on empty or busy cloud members.

**Post-lab:** run `bash scripts/main/post-lab-restore.sh` so Zalo session, Ollama, combos, and router chat are verified before stopping the host (avoids “Qwen off → case 32 / manual chat no reply” gaps).

## Active combos (when Qwen on)

| Combo | Members | Notes |
|-------|---------|--------|
| `hermes` | ≤2 Qwen chat models (cloud and/or `ollama/qwen2.5:7b`) | Round-robin |
| `classifier` | 1 Qwen chat model | Intent / multi-request split |
| `qwen-fast` | Tiny ~1.5B/1.7B when catalog has them | Empty if none |

## Recommended `ZALO_WORKFLOW_PARALLEL` by host profile

Starting recommendations for **5–10 concurrent Zalo users** with multi-request bubbles.
Validate with `test/scripts/zalo_tn_qwen_parallel_sizing.py` (Tn inject) before production.

| Profile (vCPU / RAM) | Recommended parallel | Concurrent users (guidance) | Notes |
|----------------------|----------------------|-----------------------------|--------|
| 1 / 1 GB | 2 | 1–2 | Too small for full stack + Ollama 7B |
| 1 / 2 GB | 3 | 2–3 | Ollama 7B only; expect long greeting latency |
| 2 / 2 GB | 4 | 3–5 | Minimum practical lab (current VPS class) |
| 2 / 4 GB | 6 | 5–8 | Good for mixed text + light tools |
| 3 / 6 GB | 7 | 5–9 | Between 2c/4G and 4c/8G |
| 4 / 8 GB | **8** (product default) | 5–10 | Target for multi-request Zalo |
| 4 / 16 GB | 10 | 8–12 | Headroom for weather/search tools |
| 8 / 16 GB | 12 | 10–16 | Scale Hermes replicas if SSE/queue saturates |
| 8 / 32 GB | 16 | 12–20 | Watch Omni upstream rate limits |

Rule of thumb: `parallel ≈ min(vCPU * 2, RAM_GB, 16)` then clamp to the table.
Never raise parallel alone if Omni returns 402/503 — slim combos and fail over first.

**Local Ollama 7B on CPU:** greeting inject may need `ZALO_GREETING_WAIT_S=180` (default when `OLLAMA_*` set).

## Latency snapshot (lab, 2026-08-22)

| Path | Result |
|------|--------|
| Cloud Qwen greeting inject → send ok | ~7.5–22 s E2E |
| Local Ollama 7B CPU greeting | ~18–120 s E2E (host-dependent); use longer wait |
| Short math inject | ~10–11 s E2E (cloud) |
| Mixed ≥3 requests | 4 sends; first ~10 s, last ~18 s (cloud) |

## Tests

| Script | Purpose |
|--------|---------|
| `test/scripts/qwen_combo_preflight.py` | Case 38 — key or Ollama + non-empty combos |
| `test/scripts/zalo_tn_greeting_inject.py` | Case 32 — Tn greeting |
| `test/scripts/zalo_tn_qwen_perf.py` | Latency + HW samples |
| `test/scripts/zalo_tn_qwen_parallel_sizing.py` | Recommend / probe parallel by profile |
| `test/scripts/qwen_parallel_recommend_unit.py` | Offline sizing table unit |
| `test/scripts/soul_deception_unit.py` | SOUL must not trip `deception_hide` |

Always inject as allowlisted user **Tn** via bridge `/inject-event` (id from host allowlist file — never commit).
