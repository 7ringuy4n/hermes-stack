# -*- coding: utf-8 -*-
"""Unit: skip optional scrapes when ENABLE_* is off. No host identity."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "architect" / "monitor"))
from optional_services import host_expected, monitor_metrics_on  # noqa: E402


def main() -> int:
    os.environ["ENABLE_GRAFANA"] = "0"
    os.environ["ENABLE_PROMETHEUS"] = "0"
    os.environ["ENABLE_ANTIVIRUS"] = "0"
    os.environ["ENABLE_ZALO"] = "0"
    os.environ["ENABLE_OMNIROUTER"] = "0"
    os.environ["ENABLE_OCR"] = "1"
    assert not monitor_metrics_on()
    assert not host_expected("node-exporter")
    assert not host_expected("clamav")
    assert not host_expected("zalo-api")
    assert not host_expected("omni-router")
    assert host_expected("qdrant")
    assert host_expected("ocr")
    os.environ["ENABLE_PROMETHEUS"] = "1"
    assert monitor_metrics_on()
    assert host_expected("node-exporter")
    print("optional_scrape_unit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
