# -*- coding: utf-8 -*-
"""Offline unit: recommended ZALO_WORKFLOW_PARALLEL by CPU/RAM profile."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "main"))

# Keep table in sync with docs/QWEN_PERFORMANCE.md
RECOMMENDED = {
    (1, 1): 2,
    (1, 2): 3,
    (2, 2): 4,
    (2, 4): 6,
    (3, 6): 7,
    (4, 8): 8,
    (4, 16): 10,
    (8, 16): 12,
    (8, 32): 16,
}


def recommend(vcpu: int, ram_gb: int) -> int:
    exact = RECOMMENDED.get((vcpu, ram_gb))
    if exact is not None:
        return exact
    rough = min(max(vcpu, 1) * 2, max(ram_gb, 1), 16)
    # Clamp to nearest known profile band
    bands = sorted(RECOMMENDED.items(), key=lambda x: (x[0][0], x[0][1]))
    best = bands[0][1]
    for (c, r), val in bands:
        if vcpu >= c and ram_gb >= r:
            best = val
    return min(rough, best) if rough < best else best


def main() -> int:
    assert recommend(4, 8) == 8, "product default profile"
    assert recommend(1, 1) == 2
    assert recommend(2, 4) == 6
    assert recommend(3, 6) == 7
    assert recommend(8, 32) == 16
    assert 2 <= recommend(3, 6) <= 8
    # Product default in .env.example / compose must match 4c/8G recommendation
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ZALO_WORKFLOW_PARALLEL=8" in env
    compose = (ROOT / "docker" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "ZALO_WORKFLOW_PARALLEL:-8" in compose or "ZALO_WORKFLOW_PARALLEL:-8}" in compose
    assert "ENABLE_QWEN=0" in env
    print("PASS_QWEN_PARALLEL_RECOMMEND")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
