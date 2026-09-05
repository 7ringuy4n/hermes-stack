# 02b — Operations command reference

```bash
cd /opt/assistant
bash run.sh <command> [args…]
```

## First installation

```bash
sudo timedatectl set-timezone Asia/Ho_Chi_Minh
cp .env.example .env
bash run.sh up
bash run.sh first-setup-omnirouter
bash run.sh install schedule media security notify message monitor
bash scripts/main/setup-zalo.sh
bash run.sh install-timers
```

`first-setup-omnirouter` initializes OmniRoute only. It must not run probes that
generate images or send Zalo messages. Provider/combo changes are operator
configuration; update does not replace them.

## Lifecycle

| Command | Data safety and behavior |
|---|---|
| `up` | Reconcile core and enabled-worker compose services. |
| `down` | Stop services; preserve volumes and host data. |
| `destroy` | Create and verify a backup, then remove project containers and networks. Volumes and `/data/assistant` remain. |
| `update` | Create and verify a backup, rebuild/reconcile services, clean supported obsolete environment keys, and preserve OmniRoute/OpenBao state. |
| `ps` | Show service state. |
| `logs [service]` | Read service logs. |

Clean redeploy of current data:

```bash
bash run.sh backup
bash run.sh verify
bash run.sh workers          # capture enabled workers
bash run.sh destroy
bash run.sh up               # reads retained worker state
bash run.sh ps
```

Do not remove named volumes or `/data/assistant` as part of this sequence.

## Worker lifecycle

```bash
bash run.sh install list
bash run.sh install schedule media security notify message monitor
bash run.sh uninstall notify
bash run.sh workers
```

Every mutating worker/config command backs up and verifies first. On a running
host, apply supported core settings with:

```bash
bash run.sh add-components HERMES_REPLICAS=2 --update
bash run.sh add-components ZALO_INBOUND_QUEUE=1 --update
```

## Backup and restore

```bash
bash run.sh backup
bash run.sh verify
bash run.sh verify 20260905_120000
bash run.sh restore 20260905_120000
bash run.sh migrate
```

A valid stamp covers data/config plus the OmniRoute and OpenBao components.
Reports must show presence/checksums without printing tokens or provider keys.

## Knowledge, memory, and schedule

```bash
bash run.sh auto-learn
bash run.sh learn-status
bash run.sh compact
bash run.sh optimize-memory
sudo bash run.sh install-timers
systemctl list-timers 'assistant-*'
```

Compact/optimization and ingest must prove calls through the `embedding` combo.
Scheduler tests are separate from setup and use a maximum two-minute target.

## Runtime observation

```bash
docker compose ps
docker compose logs --since 15m hermes model-router omni-router
journalctl --user -u com.hermes.zaloplugin --since '15 minutes ago'
systemctl --user status com.hermes.zaloplugin
```

Also inspect dispatcher/jobs, schedule-worker, and watchers when their test is
in scope. Classify provider quota/queue saturation separately from service
hangs and restart loops.

## Updating from `main`

```bash
cd /opt/assistant
git fetch origin
git checkout main
git pull --ff-only origin main
bash run.sh update
bash run.sh ps
```

Do not use `git reset --hard` on an operator checkout unless its local changes
have been reviewed and explicitly discarded.
