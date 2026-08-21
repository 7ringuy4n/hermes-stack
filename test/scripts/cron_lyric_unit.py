# -*- coding: utf-8 -*-
"""Unit: strip Hermes cron wrappers; quote/song hints for lyric follow-ups."""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hermes" / "main" / "plugins" / "zalo"))

from attachment import quoted_context_snip, song_hint_from_filename  # noqa: E402
from gateway_noise import strip_cron_delivery  # noqa: E402

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def test_strip_cron_delivery() -> None:
    wrapped = (
        "Cronjob Response: Hãy bắt đầu bằng lời chào 'Xin chào!'. Sau đó, thự\n"
        "(job_id: 7e5668ffaa80)\n"
        "\n"
        "Xin chào!\n\n"
        "Giá xăng E5 RON 92: 21.830\n"
        "\n"
        "To stop or manage this job, send me a new message "
        "(e.g. \"stop reminder Hãy bắt đầu bằng lời chào 'Xin chào!'. Sau đó, thự\")."
    )
    body = strip_cron_delivery(wrapped)
    assert "Xin chào!" in body, body
    assert "21.830" in body, body
    assert "Cronjob Response" not in body, body
    assert "job_id" not in body.lower(), body
    assert "To stop or manage" not in body, body
    plain = "Chào buổi sáng"
    assert strip_cron_delivery(plain) == plain
    print("PASS strip_cron_delivery body-only")


def test_song_hint() -> None:
    name = "Multo - Cup of Joe (Official Lyric Video) - Cup of Joe.mp3"
    hint = song_hint_from_filename(name)
    assert "Multo" in hint and "Cup of Joe" in hint, hint
    assert "Official" not in hint, hint
    print("PASS song_hint_from_filename")


def test_quoted_snip() -> None:
    assert "hello" in quoted_context_snip({"content": "hello world"})
    title = quoted_context_snip(
        {
            "msgType": "share.file",
            "content": {
                "title": "Multo - Cup of Joe.mp3",
                "href": "https://example/x",
            },
        }
    )
    assert "Multo" in title, title
    print("PASS quoted_context_snip")


def main() -> int:
    try:
        test_strip_cron_delivery()
        test_song_hint()
        test_quoted_snip()
    except AssertionError as e:
        print(f"FAIL {e}")
        return 1
    print("PASS cron_lyric_unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
