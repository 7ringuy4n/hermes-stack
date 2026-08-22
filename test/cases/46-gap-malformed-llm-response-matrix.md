# Case 46: Malformed LLM Response Matrix

**Gap matrix id:** Case 42 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Test model-router behavior against realistic malformed LLM output.

## Return these responses

- empty content;
- `null`;
- empty JSON;
- invalid JSON;
- truncated JSON;
- JSON inside Markdown;
- JSON with unknown fields;
- wrong data type;
- `instructions: null`;
- `instructions: "text"`;
- duplicate instructions;
- `task_hint: "chat"` when invalid;
- unknown `task_hint`;
- `reasoning_content` only;
- content + reasoning conflict;
- valid JSON followed by prose;
- HTTP 200 with an error message;
- HTTP 200 with "I cannot help";
- HTTP 429;
- HTTP 413;
- HTTP 401;
- HTTP 403.

## Pass criteria

Hermes/model-router must never treat malformed classifier output as a valid execution plan.

A classification failure must become:

- controlled fallback;
- controlled retry;
- or explicit failure.

Never execute an invented or accidental instruction.

This is especially important because the current architecture moved task decomposition into Model Router and previously had real failures around timeout-generated fake one-task plans.

---
