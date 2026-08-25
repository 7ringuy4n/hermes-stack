# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hermes" / "main" / "plugins" / "zalo"))
import channels_client as cc


def test_reject_allow_status():
    assert cc.extract_target_group_ref("nhóm đã allow (1)", {}) == ""
    assert cc.extract_target_group_ref("x", {"target_group": "đã allow (1)"}) == ""
    assert cc.extract_target_group_ref("đã allow", {}) == ""


def test_keep_real_group():
    assert cc.extract_target_group_ref("ignored", {"target_channel": "LC"}) == "LC"
    assert cc.extract_target_group_ref("gửi vào nhóm LC lúc 21:00", {}) == ""


if __name__ == "__main__":
    test_reject_allow_status()
    test_keep_real_group()
    print("OK")
