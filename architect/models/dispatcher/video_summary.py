"""Social video links — platform rules, no fetch / no summary."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

REFUSE_VI = (
    "Do quy định của YouTube, TikTok và Facebook, mình không được truy cập trực tiếp "
    "nội dung trên các nền tảng đó nên không tóm tắt hay trích lời video giúp được.\n\n"
    "Bạn xem trên app của họ, rồi hỏi mình phần cần hỗ trợ (kỹ thuật, tài liệu) nhé."
)


class VideoSummaryReq(BaseModel):
    url: str = ""
    language: Optional[str] = None
    summarize: bool = True
    max_chars: int = Field(default=14000, ge=500, le=50000)


def register_video_summary(
    app: FastAPI,
    media_dir: Path,
    whisper_transcribe: Callable[..., str],
) -> None:
    del media_dir, whisper_transcribe

    @app.post("/v1/video-summary")
    def video_summary(_req: VideoSummaryReq) -> dict[str, Any]:
        """Do not scrape YouTube / TikTok / Facebook. Same refuse as the skill."""
        return {
            "ok": False,
            "blocked": True,
            "reason": "platform_rules",
            "summary": REFUSE_VI,
            "transcript": "",
        }


def health_fields(_media_dir: Path) -> dict[str, Any]:
    return {
        "video_summary": False,
        "video_summary_policy": True,
        "youtube_cookies": False,
        "youtube_proxy": False,
    }
