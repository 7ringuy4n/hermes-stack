# Zalo SSE heal (optional component)

## Purpose

After **backup/restore** (or any event that changes Hermes container ids), the shared
`zalo_owner` / `zalo_owner.lock` files under `HERMES_DATA_DIR` can point at a **dead**
hostname. No replica then attaches to the Zalo bridge → `sseClients=0` → bot silent.
The previous watchdog only restarted the bridge, which does not fix a stale owner lock.

## Scripts

| Script | Role |
|--------|------|
| `heal-zalo-sse.sh` | Clears owner lock, restarts `zalo-proxy` + all Hermes replicas |
| `zalo-watch.sh` | Timer: if logged in but `sseClients=0` for `ZALO_WATCH_SSE_MISS` ticks, runs heal |

## Enable / disable

| Variable | Default | Meaning |
|----------|---------|---------|
| `ENABLE_ZALO` | `0` | Heal no-ops when not `1` |
| `ZALO_WATCH_RESTART_HERMES` | `1` | Allow Hermes restart on sse=0 |
| `ZALO_WATCH_CLEAR_OWNER` | `1` | Delete stale `zalo_owner*` before heal |
| `ZALO_WATCH_SSE_MISS` | `8` | Misses before heal |
| `ZALO_WATCH_SSE_COOLDOWN` | `900` | Seconds between heals |

Manual:

```bash
ENABLE_ZALO=1 bash scripts/main/heal-zalo-sse.sh
```

Restore calls heal automatically via `architect/backup-restore/lib/backup.sh`.

## Related

- [architect/backup-restore/README.md](../../architect/backup-restore/README.md)
- Hermes replica entry: `hermes/main/docker/hermes-replica-entry.sh`
