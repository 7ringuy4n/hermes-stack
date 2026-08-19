# -*- coding: utf-8 -*-
"""Turn a still image into a short H.264 mp4 Zalo can attach."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or ""


def still_to_mp4(src: Path, dest: Path, *, seconds: float = 4.0) -> None:
    """Write dest as baseline H.264 yuv420p (even dimensions, +faststart)."""
    bin_path = ffmpeg_bin()
    if not bin_path:
        raise RuntimeError("ffmpeg missing")
    sec = max(2.0, min(12.0, float(seconds)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        bin_path,
        "-y",
        "-loop",
        "1",
        "-i",
        str(src),
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
        "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
        "-b:v",
        "800k",
        "-r",
        "25",
        "-movflags",
        "+faststart",
        "-an",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=90)


def remux_mp4(src: Path, dest: Path) -> None:
    """Re-encode an existing clip so Zalo send-attachment accepts it."""
    bin_path = ffmpeg_bin()
    if not bin_path:
        raise RuntimeError("ffmpeg missing")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        bin_path,
        "-y",
        "-i",
        str(src),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "baseline",
        "-level",
        "3.1",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
        "-b:v",
        "800k",
        "-r",
        "25",
        "-movflags",
        "+faststart",
        "-an",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=90)
