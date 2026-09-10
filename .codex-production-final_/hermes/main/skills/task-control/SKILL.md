---
name: task-control
description: Stop the request currently running in a Zalo DM or group thread. Use only for explicit active-work cancellation, including a quote-reply to the request being stopped.
---

# Active request control

This is a host-owned control action. The classifier identifies the user's
semantic intent; the adapter performs cancellation before rate limiting or FIFO
admission.

- Cancel only work active in the current thread scope.
- A quoted message supplies context but never broadens cancellation to another
  DM or group.
- Do not confuse active-work cancellation with deleting or pausing schedules,
  deleting notes, rejecting a proposal, or discussing cancellation.
- Confirm success only after the host cancels the active task.
- If no request is active, do not claim that anything was stopped.
- Cancellation must release inflight, compound, and queue ownership so the next
  request can proceed.
