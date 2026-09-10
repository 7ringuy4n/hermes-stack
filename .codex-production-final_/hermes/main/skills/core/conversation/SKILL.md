---
name: conversation
description: "Maintain thread context and follow-ups. Use when the user refers to prior messages, continues a task, or asks 'what about…' without restating full context."
---

# Conversation

## Must follow

1. Treat prior turns in the thread as binding unless the user overrides.
2. Resolve pronouns ("it", "that file", "same as before") from context before acting.
3. Do not re-ask for data already provided in the thread.
4. On topic shift, confirm briefly only if ambiguity would cause wrong action.

## Sources

VoltAgent awesome-agent-skills (catalog). Pair with Memory Manager for durable facts across sessions.
