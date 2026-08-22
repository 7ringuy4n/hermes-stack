# Case 41: Restart During In-Flight Request

**Gap matrix id:** Case 37 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Detect lost work, duplicated work, corrupted sessions, and false success when Hermes or a worker dies during execution.

## Procedure

Run long operations:

- OCR
- video extraction
- web search
- image generation
- schedule workflow
- multi-item workflow
- Zalo response
- file generation

During execution:

1. Kill Hermes.
2. Repeat with model-router.
3. Repeat with workflow worker.
4. Repeat with media worker.
5. Repeat with dispatcher.
6. Restart the killed component.
7. Observe final state.

## Pass criteria

Every operation must resolve into exactly one of:

- completed;
- safely retried;
- explicitly failed.

Never:

- two successful deliveries;
- permanently stuck job;
- job silently disappearing;
- "success" without output;
- output delivered twice.

---
