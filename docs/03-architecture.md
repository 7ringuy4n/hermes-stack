# 03 — System architecture & workflows

Whole-product view of **assistant**: Hermes Agent + Memory, optional social apps, and optional workers (`WORKER_*=active|inactive`).

Each section: **Brief view** = HTML architecture panel · **Workflow** = HTML steps.

Ops: [02-components-and-commands.md](./02-components-and-commands.md) · Workers: [00-workers.md](./00-workers.md) · Components: [04-component-flows.md](./04-component-flows.md) · Core chat path: [01-workflow.md](./01-workflow.md)

---

## 0. Brief view — entire product

<table style="width:100%;border-collapse:collapse;font-family:Segoe UI,Arial,sans-serif;font-size:13px;">
  <tr>
    <td colspan="3" style="padding:12px;background:#1a1a1a;color:#fff;text-align:center;font-weight:700;">USERS — console · IDE · social-app (Zalo / Telegram / HTTP)</td>
  </tr>
  <tr>
    <td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td>
  </tr>
  <tr>
    <td colspan="3" style="padding:12px;background:#0f766e;color:#fff;text-align:center;font-weight:700;">edge (v0.5.0 default) — API Gateway · Traefik &nbsp;|&nbsp; Zalo bypasses edge</td>
  </tr>
  <tr>
    <td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td>
  </tr>
  <tr>
    <td colspan="3" style="padding:14px;background:#2563eb;color:#fff;text-align:center;font-weight:700;">hermes — Agent · skills · plugins · messages (×1 or ×2 on one node)</td>
  </tr>
  <tr>
    <td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td>
  </tr>
  <tr>
    <td colspan="3" style="padding:12px;background:#4338ca;color:#fff;text-align:center;font-weight:700;">model-router — task_hint (NORMAL fast path · CODING → 9router · never SECRET)</td>
  </tr>
  <tr>
    <td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td>
  </tr>
  <tr>
    <td style="width:34%;padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;vertical-align:top;">
      <div style="font-weight:700;margin-bottom:6px;">Core (always on)</div>
      memory · session · ingest · embed<br/>dispatcher · 9Router · model-router · backup
    </td>
    <td style="width:33%;padding:12px;background:#fff8e6;border:1px solid #f0e0b0;vertical-align:top;">
      <div style="font-weight:700;margin-bottom:6px;">Medium+</div>
      OCR · Jobs · web search<br/>file-gen · compact · OmniRouter opt.
    </td>
    <td style="width:33%;padding:12px;background:#fde8e8;border:1px solid #f0c0c0;vertical-align:top;">
      <div style="font-weight:700;margin-bottom:6px;">High only</div>
      authz · security · notify<br/>monitor opt · OpenBao · CloudDrive
    </td>
  </tr>
  <tr>
    <td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td>
  </tr>
  <tr>
    <td colspan="3" style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;">
      <b>Stores</b> — Postgres · Valkey · Qdrant &nbsp;|&nbsp; <b>Data</b> <code>/data/assistant</code> &nbsp;|&nbsp; <b>Backups</b> <code>/data/assistant/backups</code>
    </td>
  </tr>
</table>

<table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:13px;">
  <tr style="background:#f5f5f5;"><td style="padding:10px 12px;width:28%;"><b>Platform</b></td><td style="padding:10px 12px;"><code>architect/</code></td></tr>
  <tr><td style="padding:10px 12px;"><b>Agent surface</b></td><td style="padding:10px 12px;"><code>hermes/</code></td></tr>
  <tr style="background:#f5f5f5;"><td style="padding:10px 12px;"><b>Data</b></td><td style="padding:10px 12px;"><code>/data/assistant</code></td></tr>
  <tr><td style="padding:10px 12px;"><b>Backups</b></td><td style="padding:10px 12px;"><code>/data/assistant/backups</code></td></tr>
</table>

---

## 1. Profile layers

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:14px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:30%;"><b>Low</b><br/>Must chat</td>
    <td style="padding:8px;background:#eee;text-align:center;width:5%;">→</td>
    <td style="padding:14px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:30%;"><b>Medium</b><br/>+ OCR web file-gen compact</td>
    <td style="padding:8px;background:#eee;text-align:center;width:5%;">→</td>
    <td style="padding:14px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:30%;"><b>High</b><br/>+ security ACL · monitor opt · CloudDrive</td>
  </tr>
  <tr>
    <td colspan="5" style="padding:10px 12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;">
      <b>social-app</b> = attach anytime (not a profile)
    </td>
  </tr>
</table>

### Workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:14px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:30%;"><b>Low</b><br/>Must chat</td>
    <td style="padding:8px;background:#eee;text-align:center;width:5%;">→</td>
    <td style="padding:14px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:30%;"><b>Medium</b><br/>OCR · web · file-gen · compact</td>
    <td style="padding:8px;background:#eee;text-align:center;width:5%;">→</td>
    <td style="padding:14px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:30%;"><b>High</b><br/>security · ACL · monitor opt · CloudDrive · OpenBao</td>
  </tr>
</table>

- **Low:** Must only + text chat. Dispatcher on; web backends empty.
- **Medium:** + OCR, Jobs, web, file-gen, compact @ 00:00.
- **High:** + secret-probe, AV, authz, notify, **optional** monitor (Grafana↔Prometheus+exporters, Loki↔Alloy), OpenBao, CloudDrive. zalo-api with ENABLE_ZALO. Extra RAM/disk/CPU: [HARDWARE.md](./HARDWARE.md).
- **Social apps:** attach anytime — not a profile.

---

## 2. End-to-end chat (Low)

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td colspan="5" style="padding:10px;background:#1a1a1a;color:#fff;text-align:center;"><b>User</b> → console / IDE</td>
  </tr>
  <tr><td colspan="5" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td colspan="5" style="padding:12px;background:#2563eb;color:#fff;text-align:center;"><b>Hermes Agent</b></td>
  </tr>
  <tr><td colspan="5" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:20%;">session<br/><small>Valkey</small></td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:20%;">memory-manager<br/><small>Postgres</small></td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:20%;">ingest<br/><small>cite opt</small></td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:20%;">9Router<br/><small>LLM</small></td>
    <td style="padding:10px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:20%;">Qdrant<br/><small>knowledge</small></td>
  </tr>
</table>

### Workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <thead>
    <tr style="background:#1a1a1a;color:#fff;">
      <th style="padding:10px 12px;text-align:left;width:8%;">Step</th>
      <th style="padding:10px 12px;text-align:left;width:22%;">From → To</th>
      <th style="padding:10px 12px;text-align:left;">Action</th>
    </tr>
  </thead>
  <tbody>
    <tr><td style="padding:10px 12px;">1</td><td style="padding:10px 12px;">User → Hermes</td><td style="padding:10px 12px;">message</td></tr>
    <tr style="background:#fafafa;"><td style="padding:10px 12px;">2</td><td style="padding:10px 12px;">Hermes → session</td><td style="padding:10px 12px;">short-term turns (Valkey)</td></tr>
    <tr><td style="padding:10px 12px;">3</td><td style="padding:10px 12px;">Hermes → memory-manager</td><td style="padding:10px 12px;">budgeted context</td></tr>
    <tr style="background:#fafafa;"><td style="padding:10px 12px;">4</td><td style="padding:10px 12px;">Hermes → ingest <small>(opt)</small></td><td style="padding:10px 12px;">list or search knowledge (top 5)</td></tr>
    <tr><td style="padding:10px 12px;">5</td><td style="padding:10px 12px;">Hermes → 9Router</td><td style="padding:10px 12px;">completion → answer</td></tr>
    <tr style="background:#fafafa;"><td style="padding:10px 12px;">6</td><td style="padding:10px 12px;">Hermes → User</td><td style="padding:10px 12px;">one short reply</td></tr>
    <tr><td style="padding:10px 12px;">7</td><td style="padding:10px 12px;">Hermes → memory-manager</td><td style="padding:10px 12px;">async remember</td></tr>
  </tbody>
</table>

---

## 3. Knowledge (auto-learn + cite)

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Files<br/><code>/data/assistant</code><br/>media · inbound</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:28%;"><b>tools</b><br/>OCR opt · ingest · embed</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;"><b>Qdrant</b><br/>knowledge_chunks</td>
  </tr>
  <tr>
    <td colspan="5" style="padding:10px 12px;background:#2563eb;color:#fff;text-align:center;">
      Triggers: host timer <b>00:00 auto-learn</b> · Hermes skill <b>knowledge-learn</b> (cite)
    </td>
  </tr>
</table>

### Workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td colspan="3" style="padding:10px;background:#1a1a1a;color:#fff;text-align:center;">Index path</td>
  </tr>
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Files<br/>media / inbound<br/><small>auto-learn 00:00</small></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:68%;">
      High AV? → clean/skip → OCR (Med+) → ingest → embedding → <b>Qdrant knowledge_chunks</b>
    </td>
  </tr>
  <tr>
    <td colspan="3" style="padding:10px;background:#1a1a1a;color:#fff;text-align:center;">Cite path</td>
  </tr>
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;">cite / keyword</td>
    <td style="padding:8px;background:#eee;text-align:center;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;">
      knowledge-learn → list/search → hits? <b>Top 5 + rest count</b> · else <b>no info / no guess / no web on Low</b>
    </td>
  </tr>
</table>

---

## 4. Medium tools (web / OCR / file-gen)

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td colspan="4" style="padding:10px;background:#1a1a1a;color:#fff;text-align:center;">User → <b>Hermes</b></td>
  </tr>
  <tr><td colspan="4" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td style="padding:12px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:25%;"><b>dispatcher</b><br/>web search</td>
    <td style="padding:12px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:25%;"><b>ocr</b><br/>PDF / image</td>
    <td style="padding:12px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:25%;"><b>file-gen</b><br/>office outputs</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:25%;"><b>ingest</b><br/>from OCR</td>
  </tr>
  <tr>
    <td colspan="4" style="padding:10px;background:#f5f5f5;border:1px solid #ddd;text-align:center;">
      Web chain: Tavily → Firecrawl → SearXNG
    </td>
  </tr>
</table>

### Workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#1a1a1a;color:#fff;text-align:center;width:18%;">User → Hermes</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:18%;">skill</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:left;width:56%;">
      <b>research</b> → dispatcher → Tavily → Firecrawl → SearXNG<br/>
      <b>PDF</b> → ocr → ingest<br/>
      <b>file-gen</b> → office outputs
    </td>
  </tr>
</table>

---

## 5. High security inbound file

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:22%;">social-app<br/>inbound file</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:28%;"><b>security</b><br/>AV · secret-probe</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:22%;">ok → OCR / ingest / Hermes</td>
  </tr>
  <tr>
    <td colspan="5" style="padding:10px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;">
      block → refuse message · optional <b>notification</b>
    </td>
  </tr>
</table>

### Workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:20%;">Inbound file</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:24%;">av-gateway</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:24%;">security-manager</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:20%;">OCR / ingest / Hermes</td>
  </tr>
  <tr>
    <td colspan="7" style="padding:10px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;">
      infected / risk → <b>Refuse</b> → notify (optional)
    </td>
  </tr>
</table>

---

## 6. Ops / midnight jobs

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td colspan="3" style="padding:10px;background:#1a1a1a;color:#fff;text-align:center;"><b>architect / host</b> — timers · run.sh</td>
  </tr>
  <tr>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:33%;"><b>00:00</b><br/>auto-learn → ingest</td>
    <td style="padding:12px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:33%;"><b>00:00 Med+</b><br/>compact → memory</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:33%;"><b>00:30</b><br/>backup-restore</td>
  </tr>
  <tr>
    <td colspan="3" style="padding:10px;background:#f5f5f5;border:1px solid #ddd;text-align:center;">
      Stamp → <code>/data/assistant/backups</code> · High optional CloudDrive sync
    </td>
  </tr>
</table>

### Workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:32%;"><b>00:00</b><br/>auto-learn → Qdrant</td>
    <td style="padding:12px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:32%;"><b>00:00 Med+</b><br/>compact → memory-manager</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:32%;"><b>00:30</b><br/>backup → <code>/data/assistant/backups</code></td>
  </tr>
</table>

---

## 7. Memory model (short → long)

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td colspan="4" style="padding:10px;background:#2563eb;color:#fff;text-align:center;">Hermes → <b>architect / memory</b></td>
  </tr>
  <tr>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:25%;"><b>Valkey</b><br/>short-term TTL</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:25%;"><b>Postgres</b><br/>typed LTM</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:25%;"><b>Postgres</b><br/>facts</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:25%;"><b>Qdrant</b><br/>conversational</td>
  </tr>
</table>

### Workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#2563eb;color:#fff;text-align:center;width:18%;">Chat</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:26%;">Valkey TTL<br/><small>expires → short-term gone</small></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">+</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:40%;">
      Hermes reply → async remember → Postgres (+ optional Qdrant) → <b>next-day context</b>
    </td>
  </tr>
</table>

<table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:13px;">
  <thead>
    <tr style="background:#1a1a1a;color:#fff;">
      <th style="padding:10px 12px;text-align:left;">Store</th>
      <th style="padding:10px 12px;text-align:left;">Lifetime</th>
      <th style="padding:10px 12px;text-align:left;">Holds</th>
    </tr>
  </thead>
  <tbody>
    <tr><td style="padding:10px 12px;">Valkey session</td><td style="padding:10px 12px;">Hours–~1 day</td><td style="padding:10px 12px;">Recent messages</td></tr>
    <tr style="background:#fafafa;"><td style="padding:10px 12px;">Postgres / conversational Qdrant (optional)</td><td style="padding:10px 12px;">Long-term</td><td style="padding:10px 12px;">User facts</td></tr>
    <tr><td style="padding:10px 12px;">Postgres</td><td style="padding:10px 12px;">Long-term</td><td style="padding:10px 12px;">Typed Memory Manager rows</td></tr>
    <tr style="background:#fafafa;"><td style="padding:10px 12px;">Qdrant knowledge_chunks</td><td style="padding:10px 12px;">Long-term</td><td style="padding:10px 12px;">Document RAG</td></tr>
  </tbody>
</table>

---

## Related

| Doc | Content |
|---|---|
| [04-component-flows.md](./04-component-flows.md) | HTML brief view + HTML flow per component |
| [02-components-and-commands.md](./02-components-and-commands.md) | Profile tables + commands |
| [architect/README.md](../architect/README.md) | Layer index |
