"""Social video links and video generation — policy blocks; refuse text via OmniRouter."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

_REFUSE_SYSTEM: dict[str, str] = {
    "social_summary": (
        "You are Hermes assistant. The user asked to summarize, transcribe, or quote content "
        "from YouTube, TikTok, or Facebook. Policy: you must not fetch or summarize that platform content. "
        "Write a polite refusal in the user's language (Vietnamese unless the request is clearly English). "
        "Say they should watch on the native app, then ask you for technical or document help. "
        "Output ONLY the user-facing message — no quotes, labels, or markdown headings."
    ),
    "video_generate": (
        "You are Hermes assistant. The user asked to generate or create a video clip on this stack. "
        "Policy: this deployment does not generate synthetic videos. "
        "Write a polite refusal in the user's language (Vietnamese unless clearly English). "
        "Suggest a still image (infographic/poster) or an office document instead when relevant. "
        "Output ONLY the user-facing message — no quotes, labels, or markdown headings."
    ),
    "music_generate": (
        "You are Hermes assistant. The user asked to generate music or a song on this stack. "
        "Policy: this deployment does not generate music. "
        "Write a polite refusal in the user's language (Vietnamese unless clearly English). "
        "Suggest lyrics as text in a document or a still poster when relevant. "
        "Output ONLY the user-facing message — no quotes, labels, or markdown headings."
    ),
    "audio_generate": (
        "You are Hermes assistant. The user asked to generate audio, voice, or TTS as a product. "
        "Policy: this deployment does not offer user-facing audio generation. "
        "Write a polite refusal in the user's language (Vietnamese unless clearly English). "
        "Output ONLY the user-facing message — no quotes, labels, or markdown headings."
    ),
    "transcript": (
        "You are Hermes assistant. The user asked for a transcript of YouTube/music/video/audio from a URL "
        "or to download and transcribe media. Policy: refuse URL media transcription and download. "
        "Write a polite refusal in the user's language (Vietnamese unless clearly English). "
        "Attached local files may still use OCR/ASR when the stack supports them — only refuse URL/platform fetch. "
        "Output ONLY the user-facing message — no quotes, labels, or markdown headings."
    ),
}


def _messages_path() -> Path:
    return Path(
        os.environ.get(
            "DISPATCHER_MESSAGES_FILE",
            str(Path(__file__).resolve().parent / "messages" / "en.json"),
        )
    )


def _fallback_message(topic: str) -> str:
    key = f"{topic}_refuse_fallback"
    default = (
        "Video operation is not available on this stack. "
        "Try a still image or office document instead."
    )
    try:
        data = json.loads(_messages_path().read_text(encoding="utf-8"))
        return str(data.get(key) or default)
    except OSError:
        return default


def omni_refuse_message(
    *,
    topic: str,
    context: str = "",
    language: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    """Ask OmniRouter (Hermes combo) to write the user-facing refuse message."""
    meta: dict[str, Any] = {"refused": True, "topic": topic, "via_llm": False}
    system = _REFUSE_SYSTEM.get(topic) or _REFUSE_SYSTEM["social_summary"]
    lang_hint = f"\nPreferred reply language code: {language}" if language else ""
    user = (context or "User requested a blocked video operation.").strip() + lang_hint

    oa_base = (
        os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OMNIROUTER_BASE_URL")
        or "http://omni-router:20129/v1"
    ).rstrip("/")
    oa_key = (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OMNIROUTER_API_KEY")
        or ""
    ).strip()
    oa_model = (
        os.environ.get("REFUSE_MODEL")
        or os.environ.get("HERMES_MODEL")
        or os.environ.get("REFINE_MODEL")
        or "hermes"
    )

    if not oa_base or not oa_key:
        meta["fallback"] = "missing_omni_credentials"
        return _fallback_message(topic), meta

    url = f"{oa_base}/chat/completions"
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                url,
                headers={
                    "authorization": f"Bearer {oa_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": oa_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 320,
                },
            )
            r.raise_for_status()
            data = r.json()
            content = (
                ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            ).strip()
            if content:
                meta.update({"via_llm": True, "model": oa_model, "base": oa_base})
                return content, meta
            meta["fallback"] = "empty_llm_content"
    except Exception as exc:  # noqa: BLE001
        meta["fallback"] = str(exc)[:200]

    return _fallback_message(topic), meta


def policy_block_response(
    *,
    reason: str,
    message: str,
    meta: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": False,
        "blocked": True,
        "reason": reason,
        "message": message,
        "summary": message,
        "transcript": "",
        "refuse_meta": meta,
    }


class VideoSummaryReq(BaseModel):
    url: str = ""
    language: Optional[str] = None
    summarize: bool = True
    max_chars: int = Field(default=14000, ge=500, le=50000)
    context: str = ""


class VideoPolicyRefuseReq(BaseModel):
    topic: str = "video_generate"
    language: Optional[str] = None
    context: str = ""


def register_video_summary(app: FastAPI) -> None:

    @app.post("/v1/video-summary")
    def video_summary(req: VideoSummaryReq) -> dict[str, Any]:
        """Do not scrape YouTube / TikTok / Facebook — OmniRouter writes the refuse text."""
        ctx = (req.context or req.url or "").strip()
        message, meta = omni_refuse_message(
            topic="social_summary",
            context=ctx,
            language=req.language,
        )
        return policy_block_response(reason="platform_rules", message=message, meta=meta)

    @app.post("/v1/video-policy-refuse")
    def video_policy_refuse(req: VideoPolicyRefuseReq) -> dict[str, Any]:
        """Policy refuse for video-gen skill (and other blocked video intents)."""
        topic = (req.topic or "video_generate").strip() or "video_generate"
        if topic not in _REFUSE_SYSTEM:
            topic = "video_generate"
        message, meta = omni_refuse_message(
            topic=topic,
            context=req.context,
            language=req.language,
        )
        return policy_block_response(reason="video_policy", message=message, meta=meta)


def health_fields(_media_dir: Path) -> dict[str, Any]:
    return {
        "video_summary": False,
        "video_summary_policy": True,
        "video_generate_policy": True,
        "youtube_cookies": False,
        "youtube_proxy": False,
    }
