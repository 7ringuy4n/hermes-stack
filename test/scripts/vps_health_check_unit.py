#!/usr/bin/env python3
"""Static regression checks for the post-deploy health gate."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "test" / "scripts" / "vps_health_check.py").read_text(
    encoding="utf-8"
)


def main() -> int:
    assert '${OMNIROUTER_HOST_PORT:-20129}' in SOURCE
    assert "127.0.0.1:20128" not in SOURCE
    assert 'docker exec -e "OMNIROUTER_API_KEY=' not in SOURCE
    assert 'docker exec "${cid}" python3' in SOURCE
    assert "2>/dev/null || echo fail" not in SOURCE
    print("PASS vps_health_check_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
