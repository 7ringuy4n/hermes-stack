---
name: reasoning
description: "Decompose problems and choose an approach before acting. Use when the task is multi-step, ambiguous, or needs trade-off analysis before tools or code changes."
---

# Reasoning

## Must follow

1. **Understand** — restate goal and constraints in one line.
2. **Decompose** — split into ordered sub-steps; note dependencies.
3. **Choose** — pick the smallest approach that satisfies the goal; name trade-offs briefly.
4. **Act** — execute one step at a time; re-check after each major step.
5. Pair with **`core/verification`** before claiming done.

## Do not

- Jump to implementation before the goal is clear.
- Hide assumptions — state them explicitly.

## Sources

obra/superpowers planning patterns; Kodus awesome-agent-skills (catalog). See `vendor/superpowers/`.
