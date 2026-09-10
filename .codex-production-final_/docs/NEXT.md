# Next / backlog

- Keep docs and skills in **English** for the public tree.
- Prefer `scripts/main/` for supported ops; keep host-specific probes under
  `scripts/temp/` (gitignored).
- Zalo: claim / admin transfer + SSE self-heal timers are in place; extend
  notify hooks when `ENABLE_NOTIFY=active`.
- Security P1 (see [docs/SECURITY.md](./SECURITY.md)): OpenBao non-dev, pin image
  digests, per-service secrets, Docker network segmentation, CI gitleaks.
