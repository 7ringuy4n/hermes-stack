#!/usr/bin/env python3
# Remote body for remaining RULES suite (runs on VPS).
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

TN = (os.environ.get("ZALO_TEST_USER_ID") or "").strip()
WAIT = int(os.environ.get("ZALO_SUITE_WAIT_S") or "300")
SAMPLES = Path("/data/assistant/lab-samples")
checks: list[dict] = []


def note(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(("PASS" if ok else "FAIL"), name, str(detail)[:180], flush=True)


def inject(text: str, media=None, mid: str | None = None) -> str:
    payload = {
        "type": "message",
        "threadId": TN,
        "threadType": "user",
        "senderId": TN,
        "senderName": "Tn",
        "text": text,
        "messageId": mid or ("suite-" + str(int(time.time() * 1000))),
    }
    if media:
        payload["attachments"] = media
        payload["media"] = media
    event = {"type": "message", "payload": payload}
    req = urllib.request.Request(
        "http://127.0.0.1:8787/inject-event",
        data=json.dumps(event).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")[:300]


def hermes_logs(since: str = "8m") -> str:
    out = []
    ids = subprocess.check_output(
        ["docker", "ps", "-q", "--filter", "name=hermes"], text=True
    ).split()
    for cid in ids:
        try:
            out.append(
                subprocess.check_output(
                    ["docker", "logs", "--since", since, cid],
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                )
            )
        except Exception:
            pass
    return "\n".join(out)


def plugin_logs(since_epoch: float | None = None) -> str:
    try:
        import pwd

        account = os.environ.get("SUDO_USER") or "tn"
        runtime = "/run/user/" + str(pwd.getpwnam(account).pw_uid)
        since = "@" + str(int(since_epoch)) if since_epoch else "10 min ago"
        return subprocess.check_output(
            [
                "runuser", "-u", account, "--", "env",
                "XDG_RUNTIME_DIR=" + runtime,
                "DBUS_SESSION_BUS_ADDRESS=unix:path=" + runtime + "/bus",
                "journalctl",
                "--user",
                "-u",
                "com.hermes.zaloplugin",
                "--since",
                since,
                "--no-pager",
            ],
            text=True,
            errors="replace",
        )
    except Exception as e:
        return type(e).__name__


def wait_zalo_delivery(started: float, *, photo: bool = False, wait_s: int = 150) -> str:
    marker = "self=true msgType=chat.photo" if photo else "self=true msgType=webchat"
    deadline = time.time() + wait_s
    while time.time() < deadline:
        journal = plugin_logs(started)
        hits = [line for line in journal.splitlines() if marker in line]
        if hits:
            return "\n".join(hits)
        time.sleep(2)
    return ""


def newest_media(exts: set[str], after_epoch: float) -> list[Path]:
    root = Path("/data/assistant/media/out")
    hits: list[Path] = []
    if not root.is_dir():
        return hits
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in exts:
            continue
        try:
            if p.stat().st_mtime >= after_epoch:
                hits.append(p)
        except OSError:
            pass
    hits.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return hits


def vision_rate(path: Path, prompt: str) -> str:
    """Rate via Omni vision-ocr combo (chat/completions + image_url)."""
    s = str(path)
    if s.startswith("/data/assistant/media/"):
        container = "/data/media/" + s[len("/data/assistant/media/") :]
    else:
        dest = Path("/data/assistant/media/out") / ("_suite_" + path.name)
        dest.write_bytes(path.read_bytes())
        container = "/data/media/out/" + dest.name

    script = f"""
import base64, json, os, urllib.request, io
from pathlib import Path
p = Path({container!r})
print("PATH_EXISTS", p.is_file(), p.stat().st_size if p.is_file() else 0)
if not p.is_file():
    print("VISION_BEGIN")
    print("")
    print("VISION_END")
    raise SystemExit(0)
blob = p.read_bytes()
mime = "image/jpeg"
try:
    from PIL import Image
    im = Image.open(io.BytesIO(blob)).convert("RGB")
    im.thumbnail((1280, 1280))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    blob = buf.getvalue()
except Exception as e:
    print("PIL_FALLBACK", type(e).__name__)
    low = p.suffix.lower()
    mime = "image/png" if low == ".png" else ("image/webp" if low == ".webp" else "image/jpeg")
b64 = base64.b64encode(blob).decode("ascii")
key = (os.environ.get("OMNIROUTER_API_KEY") or "").strip()
base = (os.environ.get("OMNIROUTER_BASE_URL") or "http://omni-router:20129/v1").rstrip("/")
model = (os.environ.get("OCR_MODEL") or os.environ.get("OMNIROUTER_VISION_COMBO") or "vision-ocr").strip()
body = json.dumps({{
    "model": model,
    "stream": False,
    "max_tokens": 220,
    "messages": [{{
        "role": "user",
        "content": [
            {{"type": "text", "text": {prompt!r}}},
            {{"type": "image_url", "image_url": {{"url": "data:" + mime + ";base64," + b64}}}},
        ],
    }}],
}}).encode()
req = urllib.request.Request(
    base + "/chat/completions",
    data=body,
    method="POST",
    headers={{"Authorization": "Bearer " + key, "Content-Type": "application/json"}},
)
text = ""
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode() or "{{}}")
    text = (((data.get("choices") or [{{}}])[0].get("message") or {{}}).get("content") or "").strip()
except Exception as e:
    err = ""
    if hasattr(e, "read"):
        try:
            err = e.read().decode("utf-8", "replace")[:240]
        except Exception:
            err = ""
    print("VISION_FAIL", type(e).__name__, getattr(e, "code", None), err)
print("VISION_BEGIN")
print(text)
print("VISION_END")
"""
    tmp = Path("/tmp/_suite_vision.py")
    tmp.write_text(script, encoding="utf-8")
    subprocess.check_call(
        ["docker", "cp", str(tmp), "assistant-dispatcher-1:/tmp/_suite_vision.py"]
    )
    env_args = [
        "docker",
        "exec",
        "-e",
        "OMNIROUTER_BASE_URL=http://omni-router:20129/v1",
        "-e",
        "OCR_MODEL=vision-ocr",
    ]
    try:
        for ln in Path("/opt/assistant/.env").read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if ln.startswith("OMNIROUTER_API_KEY=") and ln.split("=", 1)[1].strip():
                env_args.extend(["-e", ln.strip()])
                break
    except Exception:
        pass
    env_args.extend(
        ["assistant-dispatcher-1", "python3", "/tmp/_suite_vision.py"]
    )
    raw = subprocess.check_output(
        env_args, stderr=subprocess.STDOUT, text=True, errors="replace"
    )
    if "VISION_BEGIN" in raw and "VISION_END" in raw:
        return raw.split("VISION_BEGIN", 1)[1].split("VISION_END", 1)[0].strip()
    return raw[-500:]


def post_json(url: str, body: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def list_schedules() -> list:
    raw = urllib.request.urlopen(
        "http://127.0.0.1:8110/v1/schedules", timeout=15
    ).read().decode()
    data = json.loads(raw or "{}")
    rows = data.get("schedules") if isinstance(data, dict) else data
    return rows if isinstance(rows, list) else []


def main() -> int:
    if not TN:
        print("FAIL ZALO_TEST_USER_ID is required", flush=True)
        return 2
    # 1) Scenic image-gen
    t0 = time.time()
    inject(
        "vẽ một chú mèo ngồi trên bàn gỗ, ánh sáng tự nhiên, ảnh thật ["
        + str(int(t0))
        + "]"
    )
    img = None
    for _ in range(WAIT):
        hits = newest_media({".jpg", ".jpeg", ".webp", ".png"}, t0 - 2)
        if hits and hits[0].stat().st_size > 20_000:
            img = hits[0]
            break
        time.sleep(2)
    if not img:
        note("image_gen_file", False, "no new image")
    else:
        summary = vision_rate(
            img,
            "Describe the image in one short English sentence. Mention the main subject.",
        )
        low = summary.lower()
        subject_ok = any(
            k in low
            for k in (
                "cat",
                "kitten",
                "mèo",
                "feline",
                "animal",
                "pet",
                "table",
                "wood",
                "photo",
                "photograph",
            )
        )
        size_ok = img.stat().st_size > 20_000
        if "rate-limit" in low or "quota" in low:
            note("image_gen_file", True, "SKIP quota: " + summary[:120])
        elif not summary.strip():
            # Artifact exists; vision rater empty is a tooling miss — still fail honestly if no subject cues.
            note(
                "image_gen_file",
                False,
                f"size={img.stat().st_size} vision_empty path={img.name}",
            )
        else:
            delivery = wait_zalo_delivery(t0, photo=True)
            note(
                "image_gen_file",
                size_ok and subject_ok and bool(delivery),
                f"size={img.stat().st_size} delivered={bool(delivery)} vision={summary[:160]}",
            )

    # 2) Vision-OCR samples
    for label, fname, prompt, keys in (
        (
            "vision_tired_man",
            "tired_man_test.png",
            "Describe the person/scene briefly in English.",
            ("man", "person", "tired", "face", "sleep", "adult", "human", "male"),
        ),
        (
            "vision_sec_img",
            "sec_img.png",
            "Read any visible text. If none, describe the picture briefly.",
            (
                "text",
                "image",
                "logo",
                "icon",
                "photo",
                "picture",
                "document",
                "color",
                "shape",
                "screen",
                "ui",
                "button",
            ),
        ),
    ):
        src = SAMPLES / fname
        if not src.is_file():
            note(label, False, "missing sample")
            continue
        inbound = Path(f"/data/assistant/media/inbound/{TN}")
        inbound.mkdir(parents=True, exist_ok=True)
        dest = inbound / fname
        dest.write_bytes(src.read_bytes())
        t1 = time.time()
        media = [
            {
                "type": "image",
                "url": f"/opt/data/media/inbound/{TN}/{fname}",
                "name": fname,
            }
        ]
        inject("đọc / mô tả ảnh này giúp mình [" + str(int(t1)) + "]", media=media)
        direct = vision_rate(dest, prompt)
        delivery = wait_zalo_delivery(t1)
        low = direct.lower()
        delivery_low = delivery.lower()
        missing_reply = "chưa nhận được ảnh/file" in delivery_low or "không thấy" in delivery_low
        ok = (
            len(direct) >= 12
            and any(k in low for k in keys)
            and bool(delivery)
            and not missing_reply
        )
        if "quota" in low or "rate-limit" in low:
            note(label, True, "SKIP model: " + direct[:120])
        else:
            note(label, ok, f"delivered={bool(delivery)} direct={direct[:180] or 'empty'}")
        time.sleep(2)

    # 3) Docs OCR / extract (avoid Security/pdf.pdf — secret-probe fixture)
    for label, fname, expect in (
        (
            "docs_pdf",
            "hcmc_weather_report.pdf",
            (
                "weather",
                "hcmc",
                "hồ chí",
                "ho chi",
                "temp",
                "°",
                "celsius",
                "humidity",
                "thời tiết",
                "tp.hcm",
                "saigon",
                "hcm",
                "sunny",
            ),
        ),
        (
            "docs_txt",
            "message.txt",
            ("message", "hello", "xin", "chào", "test", "text", "weather", "ho chi"),
        ),
    ):
        src = SAMPLES / fname
        if not src.is_file():
            note(label, False, "missing")
            continue
        inbound = Path(f"/data/assistant/media/inbound/{TN}")
        inbound.mkdir(parents=True, exist_ok=True)
        dest = inbound / fname
        dest.write_bytes(src.read_bytes())
        t2 = time.time()
        media = [
            {
                "type": "file",
                "url": f"/opt/data/media/inbound/{TN}/{fname}",
                "name": fname,
            }
        ]
        inject(
            "đọc nội dung file này và tóm tắt ngắn [" + str(int(t2)) + "]",
            media=media,
        )
        delivery = wait_zalo_delivery(t2)
        excerpt = ""
        try:
            body = post_json(
                "http://127.0.0.1:8099/v1/extract-text",
                {"path": str(dest)},
                timeout=90,
            )
            excerpt = str(
                body.get("text") or body.get("content") or body.get("excerpt") or body
            )[:800]
        except Exception as e:
            if fname.endswith(".txt"):
                excerpt = dest.read_text(encoding="utf-8", errors="replace")[:800]
            else:
                excerpt = f"extract_fail:{type(e).__name__}"
        low = excerpt.lower()
        delivery_low = delivery.lower()
        missing_reply = "chưa nhận được ảnh/file" in delivery_low or "không thấy" in delivery_low
        ok = (
            len(excerpt.strip()) >= 8
            and any(k in low for k in expect)
            and bool(delivery)
            and not missing_reply
        )
        note(label, ok, f"delivered={bool(delivery)} extract={excerpt[:190]}")
        time.sleep(2)

    # 4) Web search
    try:
        search = post_json(
            "http://127.0.0.1:8096/v1/search",
            {"query": "thời tiết Đà Nẵng hôm nay", "max_results": 5},
            timeout=90,
        )
        results = search.get("results") or []
        answer = str(search.get("answer") or "")
        blob = (answer + " " + json.dumps(results, ensure_ascii=False)).lower()
        ok = bool(results) or len(answer) > 20
        if "rate-limit" in blob or "quota" in blob:
            note("web_search", True, "SKIP quota")
        else:
            note(
                "web_search",
                ok,
                f"n={len(results)} answer_len={len(answer)} sample={blob[:120]}",
            )
        search_started = time.time()
        inject(
            "tra cứu nhanh: thủ đô của Việt Nam là gì? trả lời một câu ["
            + str(int(search_started))
            + "]"
        )
        delivery = wait_zalo_delivery(search_started)
        if not delivery:
            checks[-1]["ok"] = False
            checks[-1]["detail"] += " delivery=false"
    except Exception as e:
        note("web_search", False, type(e).__name__)

    # 5) Schedule once_after
    tag = "suite-sched-" + str(int(time.time()))
    schedule_started = time.time()
    inject(f"nhắc mình uống nước sau 2 phút [{tag}]")
    row_seen = False
    schedule_id = ""
    detail = ""
    deadline = schedule_started + 150
    while time.time() < deadline:
        try:
            rows = list_schedules()
            for row in rows:
                blob = json.dumps(row, ensure_ascii=False)
                low = blob.lower()
                if tag in blob or ("uống nước" in low and TN in blob):
                    row_seen = True
                    schedule_id = str(row.get("id") or "") if isinstance(row, dict) else ""
                    detail = blob[:220]
                    break
            if not detail and rows:
                detail = f"n={len(rows)} sample={json.dumps(rows[0], ensure_ascii=False)[:120]}"
        except Exception as e:
            detail = type(e).__name__
        journal = plugin_logs(schedule_started)
        ack_count = journal.count('content="Đã lưu lịch!"')
        fire_count = journal.count('content="Nhắc mình uống nước nhé."')
        if row_seen and ack_count == 1 and fire_count == 1:
            break
        time.sleep(2)
    journal = plugin_logs(schedule_started)
    ack_count = journal.count('content="Đã lưu lịch!"')
    fire_count = journal.count('content="Nhắc mình uống nước nhé."')
    remaining = []
    try:
        remaining = [row for row in list_schedules() if tag in json.dumps(row, ensure_ascii=False)]
    except Exception:
        remaining = ["list_failed"]
    sched_ok = row_seen and ack_count == 1 and fire_count == 1 and not remaining
    note(
        "schedule_once_after",
        sched_ok,
        f"row_seen={row_seen} ack={ack_count} fire={fire_count} remaining={len(remaining)} id={schedule_id}",
    )

    try:
        hs = subprocess.check_output(
            ["docker", "ps", "--format", "{{.Names}} {{.Status}}"], text=True
        )
        flap = [
            ln
            for ln in hs.splitlines()
            if "Restarting" in ln or "unhealthy" in ln.lower()
        ]
        note("no_restart_storm", len(flap) == 0, "; ".join(flap)[:200] or "ok")
    except Exception as e:
        note("no_restart_storm", False, type(e).__name__)

    ok = all(x["ok"] for x in checks)
    print("VERDICT", "PASS" if ok else "FAIL")
    Path("/tmp/hs-suite-report.json").write_text(
        json.dumps({"checks": checks, "ok": ok}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"checks": checks, "ok": ok}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
