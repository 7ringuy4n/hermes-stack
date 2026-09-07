# From-scratch setup and recovery

Use this runbook on an authorized host. Commands contain placeholders only;
never paste credentials, Zalo identities, or exported secret values into a
report.

## Fresh host

```bash
# Enter the checked-out repository.
cd /opt/assistant

# Set the host clock used by logs and schedules.
sudo timedatectl set-timezone Asia/Ho_Chi_Minh

# Create the supported bootstrap configuration from non-secret defaults.
cp .env.example .env

# Install Docker only when the host does not already provide it.
sudo bash scripts/main/install-docker.sh

# Start core services; this is setup-only and sends no test traffic.
bash run.sh up

# Initialize OmniRoute shells without changing operator-managed combo members.
bash run.sh first-setup-omnirouter

# Enable every supported worker set.
bash run.sh install schedule media security notify message monitor

# Install the Zalo bridge and complete its interactive login.
bash scripts/main/setup-zalo.sh

# Install backup, compact, stack-watch, and Zalo-watch timers.
sudo bash run.sh install-timers

# Review effective workers and service health before any lab message.
bash run.sh workers
bash run.sh ps
```

## Verified backup

```bash
# Create a complete recovery stamp.
bash run.sh backup

# Verify the newest stamp without printing secret contents.
bash run.sh verify

# List retained stamps and select the exact timestamp when needed.
find /data/assistant/backups -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort

# Verify one selected stamp before a lifecycle operation.
bash run.sh verify YYYYMMDD_HHMMSS
```

The stamp includes stores, OpenBao, OmniRoute, Zalo session/identity state,
schedules, configuration, and enabled persistent volumes.

## Clean redeploy with retained data

```bash
# Capture the supported worker state before teardown.
bash run.sh workers

# Create and verify the mandatory pre-change backup.
bash run.sh backup
bash run.sh verify

# Remove project containers and networks while preserving volumes and data.
bash run.sh destroy

# Recreate core plus the retained enabled-worker set.
bash run.sh up

# Confirm the stack before sending test traffic.
bash run.sh ps
systemctl --user status com.hermes.zaloplugin --no-pager
```

## Full restore

```bash
# Stop mutable services before restoring the selected verified stamp.
bash run.sh down

# Restore all components from one exact stamp.
bash run.sh restore YYYYMMDD_HHMMSS

# Reconcile migrations and supported runtime configuration.
bash run.sh migrate
bash run.sh up

# Verify services, Zalo login, one SSE owner, timers, and router inventory.
bash run.sh ps
bash run.sh verify YYYYMMDD_HHMMSS
systemctl list-timers 'assistant-*' --all --no-pager
```

## Partial recovery boundary

```bash
# Inspect the release restore syntax.
bash run.sh help

# Create a migration pack when moving the complete stamp to another host.
bash run.sh migrate
```

The current supported restore is atomic at stamp level; `run.sh restore` does
not accept a component selector. Do not extract individual database, vault,
router, or Zalo files into a running stack. A partial recovery requires a
separate, reviewed maintenance procedure for that exact component and a fresh
verified full backup first.

## Production update from main

```bash
# Enter the checkout and confirm it has no unreviewed changes.
cd /opt/assistant
git status --short

# Fast-forward only to the verified main release.
git fetch origin
git checkout main
git pull --ff-only origin main

# Run the backup-first supported update path.
bash run.sh update

# Inspect service, timer, Zalo, Router Worker, and OmniRoute health.
bash run.sh ps
systemctl list-timers 'assistant-*' --all --no-pager
systemctl --user status com.hermes.zaloplugin --no-pager
```

## Release verification

```bash
# Run every offline unit without contacting the VPS.
SKIP_VPS=1 python3 test/scripts/run_case_index_lab.py

# Run the authorized live gate with credentials supplied only as process env.
python3 test/scripts/run_case_index_lab.py

# Remove disposable test output and Python caches after evidence is recorded.
find scripts/temp hermes/temp -mindepth 1 -delete 2>/dev/null || true
find . -type d -name __pycache__ -prune -exec rm -rf {} +
find . -type f -name '*.py[co]' -delete
```

Follow [`RULES.md`](./RULES.md) for evidence, real artifact evaluation, Zalo
DM/group isolation, owner failover, log observation, and the merge gate.
