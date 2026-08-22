# 02 — Components & commands

**Before anything else:** copy `.env.example` → `.env` and set every `CHANGE_ME` secret.

```bash
cd /opt/assistant
bash run.sh <command>
```

**Runtime note:** Optional workers use `bash run.sh install <name>` (not keys in `.env.example`). See [00-workers.md](./00-workers.md), [config/DEFAULTS.md](./config/DEFAULTS.md), and [02-commands.md](./02-commands.md).

Legend: **Yes** = included · **No** = not enabled by default · **Opt** = attach / optional flag

---

## Overview

<table>
  <colgroup>
    <col style="width:28%" />
    <col style="width:72%" />
  </colgroup>
  <tbody>
    <tr><td style="padding:10px 12px;vertical-align:top;background:#f5f5f5;"><b>Product</b></td><td style="padding:10px 12px;">Hermes Agent + Memory. Social apps (Zalo / Telegram / HTTP) are optional.</td></tr>
    <tr><td style="padding:10px 12px;vertical-align:top;background:#f5f5f5;"><b>Knob</b></td><td style="padding:10px 12px;"><code>ASSISTANT_PROFILE=low|medium|high</code> (default <b>low</b>)</td></tr>
    <tr><td style="padding:10px 12px;vertical-align:top;background:#f5f5f5;"><b>Must</b></td><td style="padding:10px 12px;">Always on — no <code>ENABLE_MEMORY</code> noise on Low</td></tr>
    <tr><td style="padding:10px 12px;vertical-align:top;background:#f5f5f5;"><b>Auto-learn</b></td><td style="padding:10px 12px;">00:00 → Qdrant (no approve). <b>Not</b> the same as compact.</td></tr>
    <tr><td style="padding:10px 12px;vertical-align:top;background:#f5f5f5;"><b>Compact</b></td><td style="padding:10px 12px;">00:00 on Medium+ only — slim skills / memory</td></tr>
    <tr><td style="padding:10px 12px;vertical-align:top;background:#f5f5f5;"><b>Backups</b></td><td style="padding:10px 12px;">Low/Med: <code>/data/assistant/backups</code> · High: local + optional CloudDrive sync</td></tr>
  </tbody>
</table>

---

## Components by profile

<table>
  <colgroup>
    <col style="width:34%" />
    <col style="width:14%" />
    <col style="width:14%" />
    <col style="width:14%" />
    <col style="width:24%" />
  </colgroup>
  <thead>
    <tr style="background:#1a1a1a;color:#fff;">
      <th style="padding:12px;text-align:left;">Component</th>
      <th style="padding:12px;text-align:center;">Low</th>
      <th style="padding:12px;text-align:center;">Medium</th>
      <th style="padding:12px;text-align:center;">High</th>
      <th style="padding:12px;text-align:left;">Role</th>
    </tr>
  </thead>
  <tbody>
    <tr style="background:#e8f4ea;">
      <td colspan="5" style="padding:10px 12px;"><b>Must — all profiles</b></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Hermes Agent</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Answers users</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">Memory Manager</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Prompt + typed memories</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Session (Valkey)</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Short-term chat (TTL)</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">Memory Manager + Postgres LTM</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Long-term user facts</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Postgres</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Structured memory SoT</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">Ingest + Embedding</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Docs → knowledge_chunks</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Dispatcher</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Tool bus (web off on Low)</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">9Router</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">LLM gateway</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Backup / restore</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">DR under /data/assistant/backups</td>
    </tr>
    <tr style="background:#e8eef8;">
      <td colspan="5" style="padding:10px 12px;"><b>Medium+</b></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">OCR</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">PDF / image text</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">Jobs worker</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Async OCR / ingest</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Web search</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Tavily → Firecrawl → SearXNG</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">File-gen</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">xlsx / docx / txt / pdf only</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Compact job</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">00:00 memory / skills tidy</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">OmniRouter</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Opt</td>
      <td style="padding:10px;text-align:center;">Opt</td>
      <td style="padding:10px 12px;">General LLM path; pairs with omni-exporter</td>
    </tr>
    <tr style="background:#f8e8e8;">
      <td colspan="5" style="padding:10px 12px;"><b>High only</b></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Secret-probe / AV / security</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Refuse secrets; scan files</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">Authz / policy / SIEM</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Roles + knowledge ACL</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Notify + Admin API</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Operator alerts / HTTP</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">Grafana / Prom / Loki / Alloy</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Opt</td>
      <td style="padding:10px 12px;">Grafana↔Prom; Loki↔Alloy (~5 GiB / ~40 GB / ~2 vCPU all optionals)</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">OpenBao</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Secrets store</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">CloudDrive</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Docs mirror + backup sync</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Traefik / OpenVPN / WhatsApp</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px 12px;">Removed / off on setup</td>
    </tr>
  </tbody>
</table>

### Social apps (attach on any profile)

<table>
  <colgroup>
    <col style="width:18%" />
    <col style="width:42%" />
    <col style="width:20%" />
    <col style="width:20%" />
  </colgroup>
  <thead>
    <tr style="background:#1a1a1a;color:#fff;">
      <th style="padding:12px;text-align:left;">App</th>
      <th style="padding:12px;text-align:left;">Path</th>
      <th style="padding:12px;text-align:center;">Default</th>
      <th style="padding:12px;text-align:left;">Enable</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding:10px 12px;">Zalo</td>
      <td style="padding:10px 12px;"><code>architect/social-app/zalo</code></td>
      <td style="padding:10px;text-align:center;">Opt</td>
      <td style="padding:10px 12px;"><code>ENABLE_ZALO=1</code></td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">Telegram</td>
      <td style="padding:10px 12px;"><code>architect/social-app/telegram</code></td>
      <td style="padding:10px;text-align:center;">Opt</td>
      <td style="padding:10px 12px;"><code>ENABLE_TELEGRAM=1</code></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">HTTP / IDE</td>
      <td style="padding:10px 12px;"><code>architect/social-app/http</code></td>
      <td style="padding:10px;text-align:center;">Opt</td>
      <td style="padding:10px 12px;">HTTP / IDE client</td>
    </tr>
  </tbody>
</table>

---

## Commands by profile

> Legacy matrix below. For current runtime commands, use [02-commands.md](./02-commands.md). `switch-profile` is removed; use `bash run.sh add-components ...`.

```bash
export ASSISTANT_PROFILE=low|medium|high
bash run.sh <command>
```

<table>
  <colgroup>
    <col style="width:28%" />
    <col style="width:12%" />
    <col style="width:12%" />
    <col style="width:12%" />
    <col style="width:36%" />
  </colgroup>
  <thead>
    <tr style="background:#1a1a1a;color:#fff;">
      <th style="padding:12px;text-align:left;">Command</th>
      <th style="padding:12px;text-align:center;">Low</th>
      <th style="padding:12px;text-align:center;">Medium</th>
      <th style="padding:12px;text-align:center;">High</th>
      <th style="padding:12px;text-align:left;">What it does</th>
    </tr>
  </thead>
  <tbody>
    <tr style="background:#e8f4ea;">
      <td colspan="5" style="padding:10px 12px;"><b>Stack</b></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;"><code>up</code> / <code>down</code> / <code>ps</code> / <code>logs</code></td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Start / stop / status / logs</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;"><code>destroy</code></td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Backup+verify, then remove project containers + networks (volumes/data kept)</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;"><code>profile</code></td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Show profile + optional flags</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;"><code>switch-profile &lt;low\|medium\|high&gt;</code></td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Backup+verify, change tier, <code>up</code> (or <code>--dry-run</code> / <code>--no-up</code>)</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;"><code>add-components KEY=VAL</code></td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Backup+verify, set <code>ENABLE_*</code>, <code>up</code></td>
    </tr>
    <tr style="background:#e8f4ea;">
      <td colspan="5" style="padding:10px 12px;"><b>Backup / restore</b></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;"><code>backup</code></td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Create stamp + LATEST</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;"><code>verify [stamp]</code></td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Check backup</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;"><code>restore [stamp]</code></td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Restore LATEST or stamp</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;"><code>migrate</code></td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Tarball for a new host</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;"><code>backup-sync-clouddrive</code></td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Copy LATEST to CloudDrive</td>
    </tr>
    <tr style="background:#e8f4ea;">
      <td colspan="5" style="padding:10px 12px;"><b>Knowledge &amp; memory</b></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;"><code>auto-learn</code></td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Docs → Qdrant (no approve)</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;"><code>learn-status</code></td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Ingest health + list hint</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;"><code>compact</code></td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Slim skills / memory (silent)</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;"><code>optimize-memory</code></td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Compact + Memory Manager / Valkey hooks</td>
    </tr>
    <tr style="background:#e8eef8;">
      <td colspan="5" style="padding:10px 12px;"><b>Timers &amp; channels</b></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;"><code>install-timers</code></td>
      <td style="padding:10px;text-align:center;">Yes*</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px 12px;">Systemd schedules</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;"><code>channel-status</code></td>
      <td style="padding:10px;text-align:center;">Opt</td>
      <td style="padding:10px;text-align:center;">Opt</td>
      <td style="padding:10px;text-align:center;">Opt</td>
      <td style="padding:10px 12px;">Social-app flags</td>
    </tr>
  </tbody>
</table>

\* Low timers = auto-learn **00:00** + backup **00:30** only (no compact).

### Timers

<table>
  <colgroup>
    <col style="width:40%" />
    <col style="width:15%" />
    <col style="width:15%" />
    <col style="width:15%" />
    <col style="width:15%" />
  </colgroup>
  <thead>
    <tr style="background:#1a1a1a;color:#fff;">
      <th style="padding:12px;text-align:left;">Timer</th>
      <th style="padding:12px;text-align:center;">When</th>
      <th style="padding:12px;text-align:center;">Low</th>
      <th style="padding:12px;text-align:center;">Medium</th>
      <th style="padding:12px;text-align:center;">High</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding:10px 12px;">assistant-auto-learn</td>
      <td style="padding:10px;text-align:center;">00:00</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">assistant-compact</td>
      <td style="padding:10px;text-align:center;">00:00</td>
      <td style="padding:10px;text-align:center;">No</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">assistant-backup</td>
      <td style="padding:10px;text-align:center;">00:30</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
      <td style="padding:10px;text-align:center;">Yes</td>
    </tr>
  </tbody>
</table>

---

## Worker quick examples (current runtime)

<table>
  <colgroup>
    <col style="width:22%" />
    <col style="width:78%" />
  </colgroup>
  <thead>
    <tr style="background:#1a1a1a;color:#fff;">
      <th style="padding:12px;text-align:left;">Setup</th>
      <th style="padding:12px;text-align:left;">Commands to run</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding:14px 12px;vertical-align:top;background:#e8f4ea;"><b>Core only</b></td>
      <td style="padding:14px 12px;"><pre style="margin:0;white-space:pre-wrap;"># in .env keep WORKER_*=inactive
bash run.sh up
bash run.sh backup &amp;&amp; bash run.sh verify
bash run.sh auto-learn
sudo bash run.sh install-timers</pre></td>
    </tr>
    <tr>
      <td style="padding:14px 12px;vertical-align:top;background:#e8eef8;"><b>Media|File worker</b></td>
      <td style="padding:14px 12px;"><pre style="margin:0;white-space:pre-wrap;">bash run.sh add-components WORKER_MEDIA_FILE=active
bash run.sh up                # start/recreate stack with overlays
bash run.sh check-media      # dispatcher / OCR / jobs / SearXNG smoke
bash run.sh auto-learn</pre></td>
    </tr>
    <tr>
      <td style="padding:14px 12px;vertical-align:top;background:#f8e8e8;"><b>Security (+ optional Monitor/OpenBao)</b></td>
      <td style="padding:14px 12px;"><pre style="margin:0;white-space:pre-wrap;">bash run.sh add-components WORKER_SECURITY=active WORKER_MONITOR=active
bash run.sh up
bash run.sh check-security</pre></td>
    </tr>
  </tbody>
</table>

---

## I want to… → command

<table>
  <colgroup>
    <col style="width:45%" />
    <col style="width:55%" />
  </colgroup>
  <thead>
    <tr style="background:#1a1a1a;color:#fff;">
      <th style="padding:12px;text-align:left;">Goal</th>
      <th style="padding:12px;text-align:left;">Command</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding:10px 12px;">Start / stop stack</td>
      <td style="padding:10px 12px;"><code>up</code> / <code>down</code> / <code>ps</code> / <code>logs</code></td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">Wipe containers + networks (keep data)</td>
      <td style="padding:10px 12px;"><code>destroy</code> then <code>up</code></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Save / recover / move server</td>
      <td style="padding:10px 12px;"><code>backup</code> → <code>verify</code> → <code>restore</code> or <code>migrate</code></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Index documents into knowledge</td>
      <td style="padding:10px 12px;"><code>auto-learn</code> (+ <code>learn-status</code>)</td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">Tidy memory (Medium+)</td>
      <td style="padding:10px 12px;"><code>compact</code> or <code>optimize-memory</code></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Schedule midnight jobs</td>
      <td style="padding:10px 12px;"><code>sudo bash run.sh install-timers</code></td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">Sync backup to Drive (High)</td>
      <td style="padding:10px 12px;"><code>backup-sync-clouddrive</code></td>
    </tr>
  </tbody>
</table>

---

## Paths

<table>
  <colgroup>
    <col style="width:30%" />
    <col style="width:70%" />
  </colgroup>
  <thead>
    <tr style="background:#1a1a1a;color:#fff;">
      <th style="padding:12px;text-align:left;">Role</th>
      <th style="padding:12px;text-align:left;">Path</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding:10px 12px;">Code (VPS)</td>
      <td style="padding:10px 12px;"><code>/opt/assistant</code></td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">Code (dev)</td>
      <td style="padding:10px 12px;"><code>D:\Onedrive\Work\assistant</code></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">Live data</td>
      <td style="padding:10px 12px;"><code>/data/assistant</code></td>
    </tr>
    <tr style="background:#fafafa;">
      <td style="padding:10px 12px;">Backups (Low/Med)</td>
      <td style="padding:10px 12px;"><code>/data/assistant/backups</code></td>
    </tr>
    <tr>
      <td style="padding:10px 12px;">CloudDrive (High)</td>
      <td style="padding:10px 12px;"><code>/data/clouddrive</code></td>
    </tr>
  </tbody>
</table>

---

## Related

- [00-profiles.md](./00-profiles.md) — short definitions  
- [02-commands.md](./02-commands.md) — commands-only detail  
- [architect/README.md](../architect/README.md) · [hermes/README.md](../hermes/README.md)
