# 04 — Component flowcharts

Each component:

1. **Brief view** — HTML architecture panel (where it sits; **THIS** highlighted)
2. **Internal workflow** — HTML steps

Whole system: [03-architecture.md](./03-architecture.md).

---

## hermes — Agent surface

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td colspan="3" style="padding:10px;background:#1a1a1a;color:#fff;text-align:center;">USERS</td>
  </tr>
  <tr><td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td colspan="3" style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;">
      <b>THIS — hermes</b><br/>Agent · skills · plugins · messages
    </td>
  </tr>
  <tr><td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:34%;">Must<br/>memory · tools · models</td>
    <td style="padding:10px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:33%;">social-app<br/>attach</td>
    <td style="padding:10px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:33%;">High<br/>authz · security · notify</td>
  </tr>
</table>

### Internal workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td colspan="5" style="padding:10px;background:#1a1a1a;color:#fff;text-align:center;">Inbound text or plugin</td>
  </tr>
  <tr><td colspan="5" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td colspan="5" style="padding:12px;background:#2563eb;color:#fff;text-align:center;">Load skills → common-rules · mode-router</td>
  </tr>
  <tr><td colspan="5" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:25%;">memory-manager<br/>context</td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:25%;">knowledge-learn<br/>+ messages UX</td>
    <td style="padding:10px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:25%;">chat · research<br/>upload</td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:25%;">9Router</td>
  </tr>
  <tr><td colspan="5" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td colspan="5" style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;">
      One short reply → plugin if social-app
    </td>
  </tr>
</table>

<table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:13px;">
  <thead>
    <tr style="background:#1a1a1a;color:#fff;">
      <th style="padding:10px 12px;text-align:left;">Piece</th>
      <th style="padding:10px 12px;text-align:left;">Path</th>
      <th style="padding:10px 12px;text-align:left;">Job</th>
    </tr>
  </thead>
  <tbody>
    <tr><td style="padding:10px 12px;">skills</td><td style="padding:10px 12px;"><code>hermes/main/skills/</code></td><td style="padding:10px 12px;">Instructions</td></tr>
    <tr style="background:#fafafa;"><td style="padding:10px 12px;">plugins</td><td style="padding:10px 12px;"><code>hermes/main/plugins/</code></td><td style="padding:10px 12px;">Channel adapters</td></tr>
    <tr><td style="padding:10px 12px;">messages</td><td style="padding:10px 12px;"><code>hermes/main/messages/</code></td><td style="padding:10px 12px;">Editable UX</td></tr>
    <tr style="background:#fafafa;"><td style="padding:10px 12px;">config</td><td style="padding:10px 12px;"><code>hermes/main/config/</code></td><td style="padding:10px 12px;">Non-secret snippets</td></tr>
  </tbody>
</table>

---

## architect / host

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td colspan="3" style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;">
      <b>THIS — host</b><br/>OS · Docker · run.sh · timers
    </td>
  </tr>
  <tr><td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:33%;">All containers</td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:33%;">auto-learn · backup · compact</td>
    <td style="padding:10px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:33%;">memory · tools · backup-restore</td>
  </tr>
</table>

### Internal workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:18%;">Prepare dirs</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:14%;">.env</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#2563eb;color:#fff;text-align:center;width:18%;">run.sh up</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:30%;">
      install-timers<br/>
      <small>auto-learn 00:00 · backup 00:30 · compact Med+</small>
    </td>
  </tr>
</table>

---

## architect / social-app

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">User<br/>Zalo · Telegram · HTTP</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;width:36%;"><b>THIS — social-app</b><br/>pack normalize</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">hermes plugins<br/>(± security High)</td>
  </tr>
</table>

### Internal workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:16%;">User</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#2563eb;color:#fff;text-align:center;width:22%;">social-app pack<br/><small>normalize text/media</small></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:22%;">High?<br/>AV / secret-probe</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:20%;">Hermes → pack → User</td>
  </tr>
  <tr>
    <td colspan="7" style="padding:10px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;">
      block → Refuse + notify
    </td>
  </tr>
</table>

Packs: `zalo/` · `telegram/` · `http/` — attach with flags, not profiles.

---

## architect / authentication (High)

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:22%;">Request</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#fde8e8;border:3px solid #fbbf24;text-align:center;width:36%;"><b>THIS — authentication</b><br/>workspace · role · resource ACL</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:22%;">allow → Hermes<br/>deny → Stop</td>
  </tr>
</table>

### Internal workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:14%;">Request</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:16%;">Principal</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:22%;">Workspace ACL<br/><small>DENY default</small></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:16%;">Role → Resource ACL</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:14%;">Hermes / Stop</td>
  </tr>
</table>

---

## architect / security (High)

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:22%;">Inbound<br/>file / probe</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#fde8e8;border:3px solid #fbbf24;text-align:center;width:36%;"><b>THIS — security</b><br/>AV · secret-probe · SIEM</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:22%;">ok → tools / hermes<br/>block → notify</td>
  </tr>
</table>

### Internal workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:20%;">File or text</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:18%;">Type?</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fde8e8;border:1px solid #f0c0c0;text-align:left;width:50%;">
      <b>text</b> → secret-probe → hit? Refuse + notify<br/>
      <b>file</b> → av-gateway → security-manager → clean Continue · risk Refuse + notify
    </td>
  </tr>
</table>

---

## architect / memory

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td colspan="4" style="padding:10px;background:#1a1a1a;color:#fff;text-align:center;">hermes</td>
  </tr>
  <tr><td colspan="4" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td colspan="4" style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;">
      <b>THIS — memory</b> · memory-manager · session · mem0
    </td>
  </tr>
  <tr><td colspan="4" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:25%;">Valkey</td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:25%;">Postgres</td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:25%;">mem0</td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:25%;">Qdrant conversational</td>
  </tr>
</table>

### Internal workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#2563eb;color:#fff;text-align:center;width:18%;">Chat turn</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:26%;">session → Valkey</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">+</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:40%;">
      memory-manager → Postgres · mem0 → Qdrant<br/>
      budgeted context · async remember
    </td>
  </tr>
</table>

Valkey = today. Mem0/Postgres = next month.

---

## architect / tools

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:10px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:22%;">media · inbound<br/>CloudDrive High</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#fff8e6;border:3px solid #fbbf24;text-align:center;width:36%;"><b>THIS — tools</b><br/>ingest · OCR · Jobs · embed</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:22%;">Qdrant<br/>knowledge</td>
  </tr>
  <tr>
    <td colspan="5" style="padding:10px;background:#2563eb;color:#fff;text-align:center;">Also: Hermes cite · embedding via 9Router</td>
  </tr>
</table>

### Internal workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:18%;">Sources</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;width:20%;">OCR Med+?<br/><small>yes → ocr</small></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:22%;">ingest → embedding</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:20%;">knowledge_chunks<br/><small>Top 5 + rest</small></td>
  </tr>
  <tr>
    <td colspan="7" style="padding:10px;background:#f5f5f5;border:1px solid #ddd;text-align:center;">
      jobs dashed into OCR/ingest · cite list/search hits ingest
    </td>
  </tr>
</table>

---

## architect / models

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:22%;">hermes<br/>+ embedding</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#e8f4ea;border:3px solid #fbbf24;text-align:center;width:36%;"><b>THIS — models</b><br/>9Router · dispatcher</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:22%;">LLM providers<br/>web Med+</td>
  </tr>
</table>

### Internal workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#2563eb;color:#fff;text-align:center;width:18%;">Hermes</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:22%;">9Router → Providers</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">+</td>
    <td style="padding:12px;background:#fff8e6;border:1px solid #f0e0b0;text-align:left;width:44%;">
      dispatcher<br/>
      <b>Low</b> → no web<br/>
      <b>Med+</b> → Tavily → Firecrawl → SearXNG
    </td>
  </tr>
</table>

---

## architect / notification (High)

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">ingest · security<br/>admin-api · ops</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#fde8e8;border:3px solid #fbbf24;text-align:center;width:36%;"><b>THIS — notification</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Admin DM / log<br/>hermes/main/messages</td>
  </tr>
</table>

### Internal workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:22%;">Event</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:28%;">notify service</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:38%;">Admin · message templates</td>
  </tr>
</table>

---

## architect / admin-api (High / channel)

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">Operator /<br/>social admin cmd</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#fde8e8;border:3px solid #fbbf24;text-align:center;width:36%;"><b>THIS — admin-api</b></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:28%;">allowlists · learn<br/>± notification</td>
  </tr>
</table>

### Internal workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:20%;">Operator</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:24%;">admin-api</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:40%;">Allowlists · Learn helpers · notify optional</td>
  </tr>
</table>

---

## architect / backup-restore (Must)

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td colspan="3" style="padding:10px;background:#1a1a1a;color:#fff;text-align:center;">host run.sh / timers</td>
  </tr>
  <tr><td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td colspan="3" style="padding:14px;background:#2563eb;color:#fff;text-align:center;border:3px solid #fbbf24;">
      <b>THIS — backup-restore</b>
    </td>
  </tr>
  <tr><td colspan="3" style="padding:4px;background:#eee;text-align:center;color:#666;">▼</td></tr>
  <tr>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:33%;">Postgres · Qdrant · Valkey</td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:33%;"><code>/data/assistant</code></td>
    <td style="padding:10px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:33%;">CloudDrive High</td>
  </tr>
</table>

### Internal workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#2563eb;color:#fff;text-align:center;width:22%;">backup / restore</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:30%;"><code>/data/assistant/backups</code></td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:32%;">Postgres · Qdrant · Valkey · data dir</td>
  </tr>
  <tr>
    <td colspan="5" style="padding:10px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;">
      High: <code>backup-sync-clouddrive</code> → stamp → <code>/data/clouddrive</code>
    </td>
  </tr>
</table>

**Tested (2026-08-16):** High profile round-trip `backup` → `verify` → `restore` with canary file and post-restore health (gateway, Zalo SSE, Postgres, Valkey, Hermes×2). Details: [architect/backup-restore/README.md](../architect/backup-restore/README.md) · sizing: [HARDWARE.md](./HARDWARE.md).

---

## architect / monitor (High)

### Brief view

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">All services<br/>health · metrics · logs</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:14px;background:#fde8e8;border:3px solid #fbbf24;text-align:center;width:36%;"><b>THIS — monitor</b><br/>Prom · Loki · Alloy · Grafana</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">localhost / SSH</td>
  </tr>
</table>

### Internal workflow

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#f5f5f5;border:1px solid #ddd;text-align:center;width:28%;">health · metrics · logs</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:20%;">Prometheus</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">+</td>
    <td style="padding:12px;background:#fde8e8;border:1px solid #f0c0c0;text-align:center;width:16%;">Loki</td>
    <td style="padding:8px;background:#eee;text-align:center;width:4%;">→</td>
    <td style="padding:12px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;width:16%;">Grafana</td>
  </tr>
</table>

---

## Cross-links

| Layer README | Section |
|---|---|
| [architect/memory](../architect/memory/README.md) | memory |
| [architect/tools](../architect/tools/README.md) | tools |
| [architect/models](../architect/models/README.md) | models |
| [architect/social-app](../architect/social-app/README.md) | social-app |
| [architect/security](../architect/security/README.md) | security |
| [hermes](../hermes/README.md) | hermes |
