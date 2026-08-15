"""Security Manager — inbound file/code gate (static + YARA + AV + LLM judge + sandbox).

User-facing risk message (no stack traces):
  "File contains risks so it cannot be extracted to inspect information inside."
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import tarfile
import tempfile
import zipfile
from enum import Enum
from typing import Any, Optional

import httpx
from fastapi import FastAPI, File, Form, UploadFile
from pydantic import BaseModel, Field

AV_URL = os.environ.get("AV_GATEWAY_URL", "http://av-gateway:8098").rstrip("/")
NOTIFY_URL = os.environ.get("NOTIFY_URL", "").rstrip("/")
MAX_BYTES = int(os.environ.get("SECURITY_MAX_BYTES", str(40 * 1024 * 1024)))
ENABLE_LLM_JUDGE = (
    os.environ.get("SECURITY_LLM_JUDGE", "0") == "1"
    or os.environ.get("ENABLE_LLM_JUDGE", "0") == "1"
)
ENABLE_YARA = os.environ.get("SECURITY_YARA", "1") == "1"
ENABLE_SANDBOX = os.environ.get("SECURITY_SANDBOX", "0") == "1"
EMBED_UPSTREAM = (
    os.environ.get("LLM_JUDGE_URL")
    or os.environ.get("OPENAI_BASE_URL")
    or "http://9router:20128/v1"
).rstrip("/")
API_KEY = (
    os.environ.get("LLM_JUDGE_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or os.environ.get("N9ROUTER_API_KEY")
    or ""
)
YARA_RULES = os.environ.get("SECURITY_YARA_RULES", "/app/rules/lab.yar")
SANDBOX_IMAGE = os.environ.get("SECURITY_SANDBOX_IMAGE", "python:3.12-slim")
SANDBOX_TIMEOUT = int(os.environ.get("SECURITY_SANDBOX_TIMEOUT", "8"))

USER_RISK_MSG = (
    "File contains risks so it cannot be extracted to inspect information inside."
)

DANGEROUS_IMPORTS = {
    "subprocess",
    "socket",
    "ctypes",
    "pickle",
    "shutil",
    "paramiko",
    "requests",
    "httpx",
    "urllib",
    "os",
    "pty",
    "multiprocessing",
}

# Pure-Python YARA-lite patterns (always available)
_YARA_LITE = [
    (re.compile(rb"X5O!P%@AP\[4\\PZX54\(P\^\)7CC\)7\}\$EICAR", re.I), "eicar"),
    (re.compile(rb"eval\s*\(.*exec\s*\(", re.I), "eval_exec"),
    (re.compile(rb"stratum\+tcp|xmrig|coinhive", re.I), "miner"),
    (re.compile(rb"powershell\s+-enc|FromBase64String", re.I), "ps_obfuscation"),
    (re.compile(rb"/bin/bash\s+-c.*curl.*\|.*sh", re.I), "curl_pipe_sh"),
]

app = FastAPI(title="assistant-security", version="1.1.0")


def _flow(stage: str, **fields: Any) -> None:
    parts = [f"[flow] stage={stage}"]
    for k, v in fields.items():
        if v is None:
            continue
        s = str(v).replace("\n", " ").replace('"', "'")
        if " " in s:
            s = f'"{s}"'
        parts.append(f"{k}={s}")
    print(" ".join(parts), flush=True)


class Verdict(str, Enum):
    CLEAN = "CLEAN"
    RISK = "RISK"
    ERROR = "ERROR"


class ScanResult(BaseModel):
    verdict: Verdict
    layers: dict[str, Any] = Field(default_factory=dict)
    user_message: Optional[str] = None
    quarantine: bool = False


def _notify_risk(title: str, body: str) -> None:
    if not NOTIFY_URL:
        return
    try:
        with httpx.Client(timeout=10) as c:
            c.post(
                f"{NOTIFY_URL}/v1/alert",
                json={
                    "title": title,
                    "body": body,
                    "severity": "critical",
                    "channels": ["log", "zalo", "telegram"],
                },
            )
    except Exception:
        pass


def _static_python(data: bytes, filename: str) -> dict[str, Any]:
    if not filename.endswith(".py") and b"def " not in data[:2000]:
        return {"ok": True, "skipped": True}
    try:
        tree = ast.parse(data.decode("utf-8", errors="ignore"))
    except SyntaxError as e:
        return {"ok": False, "reason": f"syntax:{e.msg}"}
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                root = n.name.split(".")[0]
                if root in DANGEROUS_IMPORTS:
                    hits.append(root)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in DANGEROUS_IMPORTS:
                hits.append(root)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec", "compile"):
                hits.append(node.func.id)
            if isinstance(node.func, ast.Attribute) and node.func.attr in (
                "system",
                "popen",
                "check_output",
            ):
                hits.append(node.func.attr)
    hits = sorted(set(hits))
    # Heuristic: many dangerous sinks → risk
    if len(hits) >= 3 or "eval" in hits or "exec" in hits:
        return {"ok": False, "reason": "dangerous_sinks", "hits": hits}
    return {"ok": True, "hits": hits}


def _archive_bomb(data: bytes, filename: str) -> dict[str, Any]:
    import io

    try:
        if filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                total = sum(i.file_size for i in zf.infolist())
                if total > MAX_BYTES * 5 or len(zf.infolist()) > 5000:
                    return {"ok": False, "reason": "archive_limits"}
        elif filename.endswith((".tar", ".tar.gz", ".tgz")):
            mode = "r:gz" if filename.endswith(("gz", "tgz")) else "r:"
            with tarfile.open(fileobj=io.BytesIO(data), mode=mode) as tf:
                members = tf.getmembers()
                total = sum(m.size for m in members)
                if total > MAX_BYTES * 5 or len(members) > 5000:
                    return {"ok": False, "reason": "archive_limits"}
    except Exception:
        return {"ok": True, "skipped": True}
    return {"ok": True}


def _yara_scan(data: bytes, filename: str) -> dict[str, Any]:
    if not ENABLE_YARA:
        return {"ok": True, "skipped": True}
    hits: list[str] = []
    for rx, name in _YARA_LITE:
        if rx.search(data):
            hits.append(name)
    # Prefer YARA-X (yara_x) then libyara
    try:
        import yara_x  # type: ignore

        if os.path.isfile(YARA_RULES):
            with open(YARA_RULES, "r", encoding="utf-8", errors="ignore") as f:
                src = f.read()
            rules = yara_x.compile(src)
            scanner = yara_x.Scanner(rules)
            for m in scanner.scan(data).matching_rules:
                hits.append(getattr(m, "identifier", None) or str(m))
    except Exception:
        try:
            import yara  # type: ignore

            if os.path.isfile(YARA_RULES):
                rules = yara.compile(filepath=YARA_RULES)
                matches = rules.match(data=data)
                hits.extend(m.rule for m in matches)
        except Exception:
            pass
    hits = sorted(set(str(h) for h in hits if h))
    if hits:
        return {"ok": False, "reason": "yara_hit", "hits": hits, "engine": "yara"}
    return {"ok": True, "hits": [], "engine": "yara"}


def _sandbox_detonate(data: bytes, filename: str) -> dict[str, Any]:
    """Network-less docker detonation with optional strace syscall watch."""
    if not ENABLE_SANDBOX:
        return {"ok": True, "skipped": True}
    if not (filename.endswith(".py") or filename.endswith(".sh")):
        return {"ok": True, "skipped": True, "reason": "not_script"}
    if not os.path.exists("/var/run/docker.sock"):
        return {"ok": True, "skipped": True, "reason": "no_docker_sock"}
    use_strace = os.environ.get("SECURITY_SANDBOX_STRACE", "1") == "1"
    try:
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, filename.replace("/", "_"))
            with open(path, "wb") as f:
                f.write(data[: 512 * 1024])
            inner = (
                ["strace", "-f", "-e", "trace=network,file", "-o", "/tmp/strace.log", "timeout", str(SANDBOX_TIMEOUT)]
                if use_strace
                else ["timeout", str(SANDBOX_TIMEOUT)]
            )
            if filename.endswith(".py"):
                inner += ["python", "/sample"]
            else:
                inner += ["sh", "/sample"]
            # image with strace when available
            image = os.environ.get("SECURITY_SANDBOX_IMAGE", "python:3.12-slim")
            prep = []
            if use_strace:
                prep = ["sh", "-c", "apt-get update -qq && apt-get install -y -qq strace >/dev/null 2>&1; " + " ".join(inner)]
                cmd_inner = prep
            else:
                cmd_inner = inner
            cmd = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--memory",
                "256m",
                "--cpus",
                "0.5",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,size=64m",
                "-v",
                f"{path}:/sample:ro",
                image,
            ] + cmd_inner
            r = subprocess.run(cmd, capture_output=True, timeout=SANDBOX_TIMEOUT + 45)
            out = (r.stdout or b"") + (r.stderr or b"")
            # syscall / egress markers
            bad = re.search(
                rb"connect\(|socket\(|Network is unreachable|clone\(|ptrace|curl |wget |nc |/etc/passwd",
                out,
                re.I,
            )
            if bad and r.returncode not in (0, 124):
                return {
                    "ok": False,
                    "reason": "sandbox_suspicious",
                    "detail": out[:300].decode(errors="ignore"),
                    "strace": use_strace,
                }
            if bad and b"connect(" in out:
                return {"ok": False, "reason": "sandbox_network_syscall", "strace": use_strace}
            return {"ok": True, "exit": r.returncode, "strace": use_strace}
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "sandbox_timeout"}
    except Exception as e:
        return {"ok": True, "skipped": True, "reason": str(e)[:80]}


def _clam_via_gateway(data: bytes, filename: str, session_id: str) -> dict[str, Any]:
    if not AV_URL:
        return {"ok": True, "skipped": True}
    try:
        with httpx.Client(timeout=120) as c:
            # health
            if c.get(f"{AV_URL}/health").status_code != 200:
                return {"ok": True, "skipped": True, "reason": "av_down"}
            files = {"file": (filename, data)}
            r = c.post(f"{AV_URL}/v1/scan", data={"session_id": session_id}, files=files)
            if r.status_code >= 400:
                return {"ok": False, "reason": "av_error"}
            # poll once
            sid = session_id
            st = c.get(f"{AV_URL}/v1/sessions/{sid}/ready")
            if st.status_code == 200 and st.json().get("blocked"):
                return {"ok": False, "reason": "infected"}
            return {"ok": True, "detail": st.json() if st.status_code == 200 else {}}
    except Exception:
        return {"ok": True, "skipped": True}


def _llm_judge(filename: str, excerpt: str) -> dict[str, Any]:
    if not ENABLE_LLM_JUDGE or not API_KEY:
        return {"ok": True, "skipped": True}
    prompt = (
        "You are a security judge. Reply ONLY CLEAN or RISK.\n"
        f"Filename: {filename}\n"
        f"Excerpt:\n{excerpt[:3000]}\n"
    )
    try:
        with httpx.Client(timeout=45) as c:
            r = c.post(
                f"{EMBED_UPSTREAM}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={
                    "model": os.environ.get("SECURITY_JUDGE_MODEL", "hermes"),
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 8,
                },
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].upper()
            if "RISK" in text:
                return {"ok": False, "reason": "llm_judge_risk"}
            return {"ok": True}
    except Exception:
        return {"ok": True, "skipped": True}


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "av": AV_URL,
        "llm_judge": ENABLE_LLM_JUDGE,
        "yara": ENABLE_YARA,
        "sandbox": ENABLE_SANDBOX,
    }


@app.post("/v1/scan")
async def scan(
    session_id: str = Form("default"),
    file: UploadFile = File(...),
) -> ScanResult:
    data = await file.read()
    filename = file.filename or "upload.bin"
    layers: dict[str, Any] = {}

    if len(data) > MAX_BYTES:
        return ScanResult(
            verdict=Verdict.RISK,
            layers={"size": {"ok": False}},
            user_message=USER_RISK_MSG,
            quarantine=True,
        )

    layers["archive"] = _archive_bomb(data, filename)
    layers["static"] = _static_python(data, filename)
    layers["yara"] = _yara_scan(data, filename)
    layers["antivirus"] = _clam_via_gateway(data, filename, session_id)
    layers["llm_judge"] = _llm_judge(
        filename, data[:4000].decode("utf-8", errors="ignore")
    )
    layers["sandbox"] = _sandbox_detonate(data, filename)

    risk = any(
        isinstance(v, dict) and v.get("ok") is False for v in layers.values()
    )
    if risk:
        _notify_risk("Security risk blocked", f"{filename}: {layers}")
        av = layers.get("antivirus") or {}
        _flow(
            "security_scan",
            session_id=session_id,
            filename=filename,
            size=len(data),
            verdict=Verdict.RISK,
            av_ok=av.get("ok") if isinstance(av, dict) else av,
        )
        return ScanResult(
            verdict=Verdict.RISK,
            layers=layers,
            user_message=USER_RISK_MSG,
            quarantine=True,
        )
    av = layers.get("antivirus") or {}
    _flow(
        "security_scan",
        session_id=session_id,
        filename=filename,
        size=len(data),
        verdict=Verdict.CLEAN,
        av_ok=av.get("ok") if isinstance(av, dict) else av,
    )
    return ScanResult(verdict=Verdict.CLEAN, layers=layers)


class UrlScanReq(BaseModel):
    url: str
    session_id: str = "default"


@app.post("/v1/scan-url")
def scan_url(req: UrlScanReq) -> ScanResult:
    """Download then scan — used before clone/fetch into the server."""
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as c:
            r = c.get(req.url)
            r.raise_for_status()
            data = r.content
            filename = req.url.rstrip("/").split("/")[-1] or "download.bin"
    except Exception:
        return ScanResult(
            verdict=Verdict.ERROR,
            layers={"download": {"ok": False}},
            user_message="Could not fetch the file safely.",
        )
    return _scan_bytes(data, filename, req.session_id)


def _scan_bytes(data: bytes, filename: str, session_id: str) -> ScanResult:
    layers: dict[str, Any] = {
        "archive": _archive_bomb(data, filename),
        "static": _static_python(data, filename),
        "yara": _yara_scan(data, filename),
        "antivirus": _clam_via_gateway(data, filename, session_id),
        "llm_judge": _llm_judge(filename, data[:4000].decode("utf-8", errors="ignore")),
        "sandbox": _sandbox_detonate(data, filename),
    }
    if any(isinstance(v, dict) and v.get("ok") is False for v in layers.values()):
        _notify_risk("Security risk blocked", f"{filename}")
        return ScanResult(
            verdict=Verdict.RISK,
            layers=layers,
            user_message=USER_RISK_MSG,
            quarantine=True,
        )
    return ScanResult(verdict=Verdict.CLEAN, layers=layers)
