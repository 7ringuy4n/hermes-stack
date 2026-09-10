---
name: quiet-delivery
description: "Never send process/status/error envelopes to chat users. Final result only. Use for every Zalo/Telegram/Lark turn."
---

# Quiet delivery (result only)

## Goal

While a request is running, **do not** send any status, progress, tool, retry, or exception text to the user. Deliver **only** the finished answer and/or media.

## Never send to the user

- Progress: `Working`, `iteration N/M`, `receiving stream response`, elapsed-minute status
- Tool narration: `web_search`, `execute_code`, “let me…”, “now I…”
- Provider failures / gateway diagnostics / stack traces / “check gateway logs”
- Busy/interrupt tips, `/busy`, approval/resume, session-restored, compaction notices
- Hermes cron wrappers: `Cronjob Response: …`, `(job_id: …)`, or
  `To stop or manage this job…` — send **only the body** of a due lịch

Those lines are **internal**. Stay silent until there is a real result.

## Do send

- The requested answer (text and/or file)
- One short user-facing failure from `messages/ux.json` only when the job truly cannot complete (no raw provider text)

## Related

- `communication/zalo-channel` — Zalo wording
- `core/scheduling` / `schedule` — due payloads; never Hermes CLI cron wrappers
- `media-out` / `image-gen` — file turns
- Adapter strips residual cron wrappers and status frames in code; this skill stops them at the source
- Outbound LLM filter prompt SoT: `hermes/main/skills/outbound/outbound.json` (`POST /v1/outbound`)
