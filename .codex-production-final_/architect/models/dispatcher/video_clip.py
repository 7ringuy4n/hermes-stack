# -*- coding: utf-8 -*-
"""Turn a still image into a short H.264 mp4 Zalo can attach."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

# Zalo sendVideo wants H.264 yuv420p (not jpeg-range yuvj), even size, AAC audio.
ZALO_VF = (
    "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease,"
    "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"
)
# Safety floor so ffmpeg gets a non-empty clip. Length comes from the caller.
VIDEO_SECONDS_MIN = 1.0
# Hard cap (2 minutes). Caller/API `seconds` decides anything below this.
VIDEO_SECONDS_MAX = 120.0


def ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or ""


def video_seconds_max() -> float:
    try:
        raw = float(os.environ.get("VIDEO_SECONDS_MAX") or VIDEO_SECONDS_MAX)
    except (TypeError, ValueError):
        raw = VIDEO_SECONDS_MAX
    return max(VIDEO_SECONDS_MIN, min(VIDEO_SECONDS_MAX, raw))


def clamp_seconds(seconds: float | None) -> float:
    try:
        sec = float(seconds)
    except (TypeError, ValueError):
        sec = VIDEO_SECONDS_MIN
    return max(VIDEO_SECONDS_MIN, min(video_seconds_max(), sec))


def _run(cmd: list[str], *, timeout: float = 90) -> None:
    subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)


def still_to_mp4(src: Path, dest: Path, *, seconds: float = 4.0) -> None:
    """Write dest as baseline H.264 yuv420p + silent AAC (even dimensions, +faststart)."""
    bin_path = ffmpeg_bin()
    if not bin_path:
        raise RuntimeError("ffmpeg missing")
    sec = clamp_seconds(seconds)
    dest.parent.mkdir(parents=True, exist_ok=True)
    encode_timeout = max(90.0, sec * 4.0 + 60.0)
    cmd = [
        bin_path,
        "-y",
        "-loop",
        "1",
        "-i",
        str(src),
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=mono:sample_rate=44100",
        "-t",
        f"{sec:.1f}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "baseline",
        "-level",
        "3.1",
        "-vf",
        ZALO_VF,
        "-b:v",
        "800k",
        "-r",
        "25",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    _run(cmd, timeout=encode_timeout)


def remux_mp4(src: Path, dest: Path) -> None:
    """Re-encode an existing clip so Zalo sendVideo accepts it."""
    bin_path = ffmpeg_bin()
    if not bin_path:
        raise RuntimeError("ffmpeg missing")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        bin_path,
        "-y",
        "-i",
        str(src),
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=mono:sample_rate=44100",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "baseline",
        "-level",
        "3.1",
        "-vf",
        ZALO_VF,
        "-b:v",
        "800k",
        "-r",
        "25",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    _run(cmd, timeout=180)


def write_video_thumb(src: Path, dest: Path) -> None:
    """First frame jpeg for zca-js sendVideo thumbnailUrl."""
    bin_path = ffmpeg_bin()
    if not bin_path:
        raise RuntimeError("ffmpeg missing")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        bin_path,
        "-y",
        "-i",
        str(src),
        "-frames:v",
        "1",
        "-q:v",
        "4",
        str(dest),
    ]
    _run(cmd)
