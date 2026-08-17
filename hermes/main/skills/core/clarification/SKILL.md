---
name: clarification
description: "Ask questions ONLY when required information is missing and blocks progress. Use when specs are underspecified — not for preference fishing or obvious defaults."
---

# Clarification

## Ask when (all true)

- A **required** input is missing (target file, environment, scope, acceptance criteria).
- Reasonable defaults would **change the outcome materially**.
- You cannot infer safely from repo context or the current message.

## Do not ask when

- The user gave enough to start (do the obvious default, note assumption).
- The question is stylistic unless they asked for options.
- You need confirmation of work you should verify yourself.

## How to ask

- **One** compact block: numbered questions, multiple-choice when possible.
- Propose your **default assumption** if they skip answering.

## Sources

Trail of Bits `ask-questions-if-underspecified` (claude-code-config); see `vendor/trailofbits/ATTRIBUTION.md`.
