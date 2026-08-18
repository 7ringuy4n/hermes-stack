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

| Layer | Doc | Profile |
|---|---|---|
| host | [host/README.md](./host/README.md) | all |
| social-app | [social-app/README.md](./social-app/README.md) | attach |
| authentication | [authentication/README.md](./authentication/README.md) | High |
| security | [security/README.md](./security/README.md) | High |
| memory | [memory/README.md](./memory/README.md) | Must |
| tools | [tools/README.md](./tools/README.md) | Must (+ OCR/Jobs Med+) |
| models | [models/README.md](./models/README.md) | Must |
| notification | [notification/README.md](./notification/README.md) | High |
| zalo-api | [zalo-api/README.md](./zalo-api/README.md) | with Zalo (`ENABLE_ZALO`) |
| backup-restore | [backup-restore/README.md](./backup-restore/README.md) | Must |
| monitor | [monitor/README.md](./monitor/README.md) | High optional (Grafana↔Prometheus+exporters, Loki↔Alloy) |
| edge | [edge/README.md](./edge/README.md) | Traefik / OpenVPN |
| gateway | [gateway/README.md](./gateway/README.md) | API Gateway |

Hermes product surface (skills, messages, plugins): [../hermes/README.md](../hermes/README.md).
