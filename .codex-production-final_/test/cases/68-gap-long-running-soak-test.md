# Case 68: Long-Running Soak Test

**Gap matrix id:** Case 64 (Production Failure Gap Test Cases v2)

**Zalo identity:** inject as allowlisted user **Tn** when the case touches inbound Zalo.

## Goal

Catch leaks and cumulative failures that short tests cannot detect.

## Duration

Minimum:

- 2 hours;
- preferably 8–24 hours for High.

Continuously generate mixed traffic:

- chat;
- media;
- OCR;
- schedules;
- web;
- Zalo;
- memory;
- workflow.

Inject random controlled failures every 10–20 minutes.

## Monitor

- RAM;
- CPU;
- Docker restart count;
- queue depth;
- Valkey keys;
- Postgres connections;
- Qdrant collection size;
- disk;
- logs;
- pending workflow jobs.

## Pass criteria

No:

- memory leak;
- queue growth without recovery;
- zombie job;
- repeated watchdog restart;
- session corruption;
- disk leak;
- unbounded temporary files.

---
