# Case 44: Poison Job / Permanently Failing Job

**Gap matrix id:** Case 40 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Prevent one impossible job from blocking the queue.

## Procedure

Create:

- invalid PDF;
- corrupt image;
- malformed DOCX;
- unsupported codec;
- impossible OCR request;
- invalid workflow instruction;
- permanently failing notification;
- model-router request that always returns 500.

Put valid jobs immediately after the failing job.

## Pass criteria

The poison job:

- reaches failed/terminal state;
- records failure;
- does not retry forever;
- does not block later jobs.

Following valid jobs must execute successfully.

---
