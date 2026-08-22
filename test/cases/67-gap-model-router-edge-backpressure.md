# Case 67: Model Router / Edge Backpressure

**Gap matrix id:** Case 63 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Determine the actual safe throughput of the stack.

## Procedure

Ramp:

`1 → 2 → 4 → 8 → 16 → 32 → 48 → 64`

Use mixed workload:

- normal chat;
- classification;
- web search;
- OCR;
- media;
- schedule;
- Zalo.

At each level record:

- p50;
- p95;
- p99;
- errors;
- queue depth;
- CPU;
- RAM;
- retries;
- model-router latency;
- Hermes latency.

## Pass criteria

Identify:

- last completely healthy concurrency;
- first degraded concurrency;
- first failure;
- recovery behavior.

Do not define a fixed "PASS = 32 users" assumption before measuring.

---
