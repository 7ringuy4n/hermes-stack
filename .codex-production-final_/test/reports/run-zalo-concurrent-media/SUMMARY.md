# Zalo concurrent text + media generation

- Timestamp: `2026-08-17 15:15:02 +0700`
- Last all-success N: **2**
- First-fail N: **4**
- Fail mode: `http_non_2xx_or_timeout`
- SSE single owner after: **True**

## Bursts (delay)

- N=2 ok=2 fail=0 elapsed_s=5.72 text={'n': 1, 'p50_ms': 5399, 'p95_ms': 5399, 'max_ms': 5399, 'min_ms': 5399} image={'n': 1, 'p50_ms': 638, 'p95_ms': 638, 'max_ms': 638, 'min_ms': 638}
- N=4 ok=3 fail=1 elapsed_s=60.28 text={'n': 2, 'p50_ms': 10582, 'p95_ms': 60015, 'max_ms': 60015, 'min_ms': 10582} image={'n': 2, 'p50_ms': 328, 'p95_ms': 1399, 'max_ms': 1399, 'min_ms': 328}
