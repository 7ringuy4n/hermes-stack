#!/usr/bin/env python3
"""Contract check for acknowledgement-backed Zalo delivery history."""
from __future__ import annotations

import ast
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    source = (root / "hermes" / "main" / "plugins" / "zalo" / "adapter.py").read_text(encoding="utf-8")
    ast.parse(source)
    error_guard = source.index('if res.get("error"):\n                return SendResult(success=False')
    delivery = source.index('event="delivered"', error_guard)
    success = source.index('return SendResult(success=True, message_id=msg_id)', delivery)
    assert error_guard < delivery < success
    delivery_body = source[delivery:success]
    assert '"quoted": bool(used_quote)' in delivery_body
    assert '"delivery_kind": str(meta.get("delivery_kind") or "result")' in delivery_body
    assert '"source_message_id": str(' in delivery_body
    assert 'meta.get("source_message_id")' in delivery_body
    assert 'self._as_source_message_id.get()' in delivery_body
    schedule_start = source.index("    async def _as_schedule_fire_verbatim(")
    schedule_end = source.index("    async def _as_gate_announce(", schedule_start)
    schedule_body = source[schedule_start:schedule_end]
    assert '"delivery_kind": "result"' in schedule_body
    assert 'm.get("messageId") or m.get("message_id")' in schedule_body
    guarded_start = source.index("    async def _on_inbound_guarded(")
    guarded_end = source.index("    async def _on_session_dead(", guarded_start)
    guarded_body = source[guarded_start:guarded_end]
    assert "self._as_source_message_id.set(" in guarded_body
    assert "self._as_source_message_id.reset(source_token)" in guarded_body
    helper_start = source.index("    def _as_record_attachment_delivery(")
    image_start = source.index("    async def send_image_file(", helper_start)
    document_start = source.index("    async def send_document(", image_start)
    video_start = source.index("    async def send_video(", document_start)
    voice_start = source.index("    async def send_voice(", video_start)
    chat_info_start = source.index("    async def get_chat_info(", voice_start)
    helper_body = source[helper_start:image_start]
    assert 'event="delivered"' in helper_body
    assert '"source_message_id": source_message_id' in helper_body
    assert "or self._as_source_message_id.get()" in helper_body
    assert '"attachment_kind": str(attachment_kind or "file")' in helper_body
    assert '"file_name": name' in helper_body
    assert "_as_bridge_message_id(response)" in helper_body
    assert source[image_start:document_start].count("_as_record_attachment_delivery(") == 1
    assert source[document_start:video_start].count("_as_record_attachment_delivery(") == 2
    assert source[video_start:voice_start].count("_as_record_attachment_delivery(") == 1
    assert source[voice_start:chat_info_start].count("_as_record_attachment_delivery(") == 2
    send_start = source.index("    async def send(\n")
    send_end = source.index("    async def send_typing", send_start)
    send_body = source[send_start:send_end]
    assert "used_quote = False" in send_body
    assert send_body.count("self._rewrite_gateway_user_notice(content)") == 1
    assert "self._is_gateway_noise(content)" not in send_body
    assert "self._as_agent_turn_lock = asyncio.Lock()" not in source
    assert "async with self._as_agent_turn_lock_for(tid):" in source
    assert "not lease.heartbeat_healthy()" in source
    queued = source.index("async def _as_run_queued_part")
    queued_body = source[queued:source.index("async def _as_dispatch_event", queued)]
    assert 'str(item.get("message_id") or "")' in queued_body
    assert queued_body.index('str(item.get("message_id") or "")') < queued_body.index(
        "await self.handle_message(event)"
    )
    terminal = source.index("idle = await self._as_wait_thread_idle(", queued)
    assert source.index("async with self._as_agent_turn_lock_for(tid):", queued) < terminal
    drain = source.index("async def _as_queue_drain")
    run_part = source.index("await self._as_run_queued_part(item)", drain)
    acknowledge = source.index("store.queue_ack(tid, raw)", run_part)
    assert run_part < acknowledge < queued
    print("zalo_delivery_history_unit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
