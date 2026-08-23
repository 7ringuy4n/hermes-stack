# architect

Platform layers around Hermes. Each subfolder has a **System architecture** section (where it sits + data flow) plus package details.

**Whole product:** [docs/03-architecture.md](../docs/03-architecture.md) · **Per-layer flows:** [docs/04-component-flows.md](../docs/04-component-flows.md) · **SPOFs / scale:** [docs/MULTI_NODE.md](../docs/MULTI_NODE.md)

<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tr>
    <td style="padding:12px;background:#2563eb;color:#fff;text-align:center;">Hermes</td>
    <td style="padding:8px;background:#eee;text-align:center;">→</td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;">memory</td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;">tools</td>
    <td style="padding:10px;background:#e8f4ea;border:1px solid #c5e0c8;text-align:center;">models<br/><small>model-router</small></td>
    <td style="padding:10px;background:#fff8e6;border:1px solid #f0e0b0;text-align:center;">social-app</td>
  </tr>
  <tr>
    <td colspan="6" style="padding:4px;background:#eee;text-align:center;color:#666;">▲ edge / gateway · authentication · security · host → backup-restore</td>
  </tr>
</table>

| Layer | Doc | Worker / activation |
|---|---|---|
| host | [host/README.md](./host/README.md) | core |
| social-app | [social-app/README.md](./social-app/README.md) | Message worker / attach |
| authentication | [authentication/README.md](./authentication/README.md) | Security worker |
| security | [security/README.md](./security/README.md) | Security / OpenBao worker |
| memory | [memory/README.md](./memory/README.md) | core |
| tools | [tools/README.md](./tools/README.md) | core (+ OCR/Jobs via Media worker) |
| models | [models/README.md](./models/README.md) | core (router-worker; Omni default) |
| notification | [notification/README.md](./notification/README.md) | Notify worker |
| zalo-api | [zalo-api/README.md](./zalo-api/README.md) | Message worker (`install message` / `zalo`) |
| backup-restore | [backup-restore/README.md](./backup-restore/README.md) | core |
| monitor | [monitor/README.md](./monitor/README.md) | Monitor worker (Grafana↔Prometheus+exporters, Loki↔Alloy) |
| edge | [edge/README.md](./edge/README.md) | Traefik core default · OpenVPN optional |
| gateway | [gateway/README.md](./gateway/README.md) | API Gateway (core default) |

Workers: [docs/00-workers.md](../docs/00-workers.md).

Hermes product surface (skills, messages, plugins): [../hermes/README.md](../hermes/README.md).
