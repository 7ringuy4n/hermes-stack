# Profiles (compatibility note)

Runtime product tiers (`ASSISTANT_PROFILE=low|medium|high`) are retired. The
stack has one core and independently enabled workers.

```bash
bash run.sh up
bash run.sh install schedule media notify message
bash run.sh workers
```

`switch-profile` is a disabled compatibility command. Use `install`,
`uninstall`, or `add-components` instead.

## Current router naming

The deployed routing control plane is **OmniRoute**. Historical environment,
compose-profile, volume, and command names retain the `OMNIROUTER_*` spelling
for upgrade compatibility; they do not enable a second router.

| Setting | Current meaning |
|---|---|
| `ENABLE_MODEL_ROUTER=active` | Run the task-aware compatibility proxy used by Hermes and workers. |
| `ENABLE_OMNIROUTER=active` | Run OmniRoute using the compatibility compose profile `omnirouter`. |
| `OMNIROUTER_*` | OmniRoute URL, token, combo, image, and data-volume settings. |
| `first-setup-omnirouter` | Idempotently initialize OmniRoute without replacing operator-managed combo members. |

There is no supported 9Router, legacy OmniRouter, local OCR engine, or ComfyUI
runtime path. See [06-model-routing.md](./06-model-routing.md) and
[00-workers.md](./00-workers.md).
