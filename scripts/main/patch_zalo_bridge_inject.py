#!/usr/bin/env python3
"""Idempotent patches for hermes-zalo-plugin (host bridge).

1. POST /inject-event — synthetic inbound onto the existing SSE fan-out (tests).
2. POST /media/fetch + GET /media/:id — download Zalo CDN bytes with the
   logged-in session cookies so Hermes can OCR / summarize attachments.
3. zaloClient.js quote mapping — use data.quote.* for quoted reply context
   (not the current message fields).

Restart prefers the user systemd unit (com.hermes.zaloplugin /
assistant-zalo). Orphan ``runuser`` / ``nohup`` processes that hold :8787
are cleared first so the unit stops crash-looping on EADDRINUSE.

Does not interpret user language — payloads are known bridge protocol objects.
"""
from __future__ import annotations

import os
import pwd
import re
import shutil
import subprocess
import time
from pathlib import Path

PLUGIN = Path(
    os.environ.get(
        "ZALO_PLUGIN_SERVER",
        "/usr/lib/node_modules/hermes-zalo-plugin/server.js",
    )
)
ZALO_CLIENT = Path(
    os.environ.get(
        "ZALO_PLUGIN_CLIENT",
        str(PLUGIN.parent / "zaloClient.js"),
    )
)
PORT = (os.environ.get("ZALO_PLUGIN_PORT") or "8787").strip() or "8787"
HOST_BIND = (os.environ.get("ZALO_PLUGIN_HOST") or "0.0.0.0").strip() or "0.0.0.0"

INJECT_MARKER = 'app.post("/inject-event"'
MEDIA_MARKER = "ASSISTANT_MEDIA_PROXY_v1"
QUOTE_MARKER = "ASSISTANT_QUOTE_FIX_v1"

QUOTE_SNIPPET = r"""
      // ASSISTANT_QUOTE_FIX_v1 — quoted reply must map data.quote, not current msg.
      quote: (() => {
        const q = data.quote;
        if (!q || typeof q !== "object") return null;
        return {
          content: typeof q.content === "string" ? q.content : q.content,
          msgType: q.msgType,
          propertyExt: q.propertyExt,
          uidFrom: q.ownerId || q.uidFrom,
          msgId: q.globalMsgId || q.msgId,
          cliMsgId: q.cliMsgId,
          ts: q.ts,
          ttl: q.ttl,
        };
      })(),
"""

# Broken upstream mapping: quote block reads data.content / data.msgId (current msg).
_QUOTE_BROKEN = re.compile(
    r"\n\s*quote:\s*\{\s*content:\s*typeof data\.content",
    re.S,
)
_QUOTE_BLOCK = re.compile(
    r"\n\s*quote:\s*(?:\(\(\)\s*=>\s*\{[\s\S]*?\}\)\(\)|\{[\s\S]*?\}),",
    re.S,
)

INJECT_SNIPPET = r"""
// assistant-stack: synthetic inbound onto the existing SSE fan-out (tests).
app.post("/inject-event", (req, res) => {
  if (!checkAuth(req, res)) return;
  const body = req.body || {};
  const type = body.type || "message";
  const payload = (body.payload && typeof body.payload === "object") ? body.payload : body;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return res.status(400).json({ error: "payload object required" });
  }
  pushEvent(type, payload);
  res.json({ ok: true });
});

"""

MEDIA_SNIPPET = r"""
// ASSISTANT_MEDIA_PROXY_v1 — Hermes downloads Zalo CDN media through the
// logged-in bridge session (cookies + user-agent). Without this, POST
// /media/fetch 404s and images/files never reach OCR.
// Uses top-level ESM imports (fs/path/http/https/crypto/os) — see patch imports.
const MEDIA_CACHE_DIR = path.join(
  process.env.ZALO_MEDIA_CACHE_DIR ||
    path.join(os.homedir(), ".hermes-zalo", "media-cache")
);
try { fs.mkdirSync(MEDIA_CACHE_DIR, { recursive: true }); } catch (_) {}

function _mediaMagicOk(buf) {
  if (!buf || buf.length < 4) return false;
  if (buf[0] === 0xff && buf[1] === 0xd8) return true; // jpeg
  if (buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4e && buf[3] === 0x47) return true; // png
  if (buf[0] === 0x47 && buf[1] === 0x49 && buf[2] === 0x46) return true; // gif
  if (buf[0] === 0x25 && buf[1] === 0x50 && buf[2] === 0x44 && buf[3] === 0x46) return true; // pdf
  if (buf[0] === 0x50 && buf[1] === 0x4b) return true; // zip/office
  if (buf.length >= 12 && buf.toString("ascii", 4, 8) === "ftyp") return true; // mp4/m4a
  if (buf[0] === 0x49 && buf[1] === 0x44 && buf[2] === 0x33) return true; // mp3/id3
  if (buf[0] === 0xff && (buf[1] & 0xe0) === 0xe0) return true; // mp3 frame
  return buf.length >= 64;
}

function _mediaSessionHeaders() {
  const headers = {
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    Accept: "*/*",
  };
  try {
    const raw = fs.readFileSync(CREDENTIALS_PATH, "utf8");
    const cred = JSON.parse(raw);
    if (cred && cred.userAgent) headers["User-Agent"] = String(cred.userAgent);
    let cookie = cred && cred.cookie;
    if (Array.isArray(cookie)) {
      cookie = cookie
        .map((c) => {
          if (!c) return "";
          if (typeof c === "string") return c;
          if (c.name && c.value !== undefined) return `${c.name}=${c.value}`;
          return "";
        })
        .filter(Boolean)
        .join("; ");
    } else if (cookie && typeof cookie === "object") {
      cookie = Object.entries(cookie)
        .map(([k, v]) => `${k}=${v}`)
        .join("; ");
    }
    if (cookie) headers.Cookie = String(cookie);
  } catch (_) {}
  return headers;
}

function _mediaFetchUrl(url, headers) {
  return new Promise((resolve, reject) => {
    let parsed;
    try {
      parsed = new URL(url);
    } catch (e) {
      reject(e);
      return;
    }
    const lib = parsed.protocol === "http:" ? http : https;
    const req = lib.get(
      url,
      { headers, timeout: 120000 },
      (resp) => {
        if (
          resp.statusCode >= 300 &&
          resp.statusCode < 400 &&
          resp.headers.location
        ) {
          resp.resume();
          _mediaFetchUrl(resp.headers.location, headers).then(resolve, reject);
          return;
        }
        if (resp.statusCode !== 200) {
          resp.resume();
          reject(new Error(`upstream HTTP ${resp.statusCode}`));
          return;
        }
        const chunks = [];
        resp.on("data", (c) => chunks.push(c));
        resp.on("end", () => resolve(Buffer.concat(chunks)));
        resp.on("error", reject);
      }
    );
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("upstream timeout"));
    });
  });
}

app.post("/media/fetch", async (req, res) => {
  if (!checkAuth(req, res)) return;
  const body = req.body || {};
  const url = String(body.url || "").trim();
  if (!url || !/^https?:\/\//i.test(url)) {
    return res.status(400).json({ error: "url required" });
  }
  try {
    const buf = await _mediaFetchUrl(url, _mediaSessionHeaders());
    const id = crypto.randomBytes(16).toString("hex");
    const dest = path.join(MEDIA_CACHE_DIR, id);
    fs.writeFileSync(dest, buf);
    res.json({
      ok: true,
      id,
      path: `/media/${id}`,
      size: buf.length,
      magicOk: _mediaMagicOk(buf),
      kind: body.kind || "",
      fileName: body.fileName || "",
    });
  } catch (e) {
    res.status(502).json({ error: String((e && e.message) || e) });
  }
});

app.get("/media/:id", (req, res) => {
  if (!checkAuth(req, res)) return;
  const id = String(req.params.id || "").replace(/[^a-fA-F0-9]/g, "");
  if (!id) return res.status(400).json({ error: "id required" });
  const dest = path.join(MEDIA_CACHE_DIR, id);
  if (!fs.existsSync(dest)) return res.status(404).json({ error: "not found" });
  res.sendFile(path.resolve(dest));
});

"""

MEDIA_IMPORTS = (
    ('import http from "node:http";\n', 'from "node:http"'),
    ('import https from "node:https";\n', 'from "node:https"'),
    ('import crypto from "node:crypto";\n', 'from "node:crypto"'),
    ('import os from "node:os";\n', 'from "node:os"'),
)


def _strip_all_inject(text: str) -> str:
    """Remove every assistant-stack /inject-event block (comment + handler)."""
    pattern = re.compile(
        r"\n?// assistant-stack: synthetic inbound[^\n]*\n"
        r"app\.post\(\"/inject-event\", \(req, res\) => \{.*?\n\}\);\n?",
        re.S,
    )
    return pattern.sub("\n", text)


def _ensure_media_imports(text: str) -> tuple[str, list[str]]:
    """Add ESM imports required by the media proxy (server.js is type=module)."""
    added: list[str] = []
    for stmt, needle in MEDIA_IMPORTS:
        if needle in text:
            continue
        lines = text.splitlines(keepends=True)
        last_import = -1
        for i, line in enumerate(lines):
            if line.startswith("import "):
                last_import = i
        if last_import < 0:
            continue
        lines.insert(last_import + 1, stmt)
        text = "".join(lines)
        added.append(needle)
    return text, added


def _strip_broken_media(text: str) -> str:
    """Remove a previous media proxy block (incl. CommonJS require form)."""
    pattern = re.compile(
        r"\n?// ASSISTANT_MEDIA_PROXY_v1.*?app\.get\(\"/media/:id\".*?\n\}\);\n?",
        re.S,
    )
    return pattern.sub("\n", text)


def patch_zalo_client() -> dict[str, str]:
    """Fix quoted-reply payload: Hermes needs data.quote content, not current message."""
    out: dict[str, str] = {}
    if not ZALO_CLIENT.is_file():
        return {"status": "CLIENT_MISSING", "path": str(ZALO_CLIENT)}
    text = ZALO_CLIENT.read_text(encoding="utf-8", errors="replace")
    original = text
    if QUOTE_MARKER in text:
        out["quote"] = "ALREADY"
    elif _QUOTE_BROKEN.search(text):
        text = _QUOTE_BLOCK.sub("\n" + QUOTE_SNIPPET, text, count=1)
        out["quote"] = "PATCHED"
    else:
        out["quote"] = "NO_BROKEN_PATTERN"
    if text != original:
        ZALO_CLIENT.write_text(text, encoding="utf-8")
        out["status"] = "WRITTEN"
    else:
        out["status"] = "UNCHANGED"
    return out


def patch_server() -> dict[str, str]:
    out: dict[str, str] = {}
    if not PLUGIN.is_file():
        return {"status": "PLUGIN_MISSING"}
    text = PLUGIN.read_text(encoding="utf-8", errors="replace")
    original = text

    # Collapse duplicate inject handlers from prior buggy MARKER checks.
    inj_count = text.count(INJECT_MARKER)
    if inj_count > 1:
        text = _strip_all_inject(text)
        out["inject_dedupe"] = f"had={inj_count}"

    if INJECT_MARKER not in text:
        needle = "_httpServer = app.listen("
        idx = text.find(needle)
        if idx < 0:
            out["inject"] = "LISTEN_MISSING"
        else:
            text = text[:idx] + INJECT_SNIPPET + text[idx:]
            out["inject"] = "PATCHED"
    else:
        out["inject"] = "ALREADY"

    # Replace broken CommonJS media blocks; ensure ESM imports exist.
    if MEDIA_MARKER in text and "require(" in text[text.find(MEDIA_MARKER) : text.find(MEDIA_MARKER) + 800]:
        text = _strip_broken_media(text)
        out["media_strip"] = "removed_commonjs"
    text, added_imports = _ensure_media_imports(text)
    if added_imports:
        out["media_imports"] = ",".join(added_imports)

    if MEDIA_MARKER not in text:
        needle = "_httpServer = app.listen("
        idx = text.find(needle)
        if idx < 0:
            out["media"] = "LISTEN_MISSING"
        else:
            text = text[:idx] + MEDIA_SNIPPET + text[idx:]
            out["media"] = "PATCHED"
    else:
        out["media"] = "ALREADY"

    if text != original:
        PLUGIN.write_text(text, encoding="utf-8")
        out["status"] = "WRITTEN"
    else:
        out["status"] = "UNCHANGED"
    return out


def _plugin_uid() -> int:
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "hermes-zalo-plugin/server.js"],
            text=True,
            timeout=5,
        )
        for pid in out.split():
            if not pid.isdigit():
                continue
            try:
                uid = os.stat(f"/proc/{pid}").st_uid
            except OSError:
                continue
            if uid != 0:
                return uid
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    try:
        return int((os.environ.get("ZALO_PLUGIN_UID") or "1000").strip())
    except ValueError:
        return 1000


def _systemctl_user(uid: int, *args: str) -> subprocess.CompletedProcess[str]:
    user = pwd.getpwuid(uid).pw_name
    runtime = f"/run/user/{uid}"
    if os.geteuid() == 0:
        # Prefer sudo -u + XDG_RUNTIME_DIR; -M user@ needs systemd-machined.
        cmd = [
            "sudo", "-u", user, "env",
            f"XDG_RUNTIME_DIR={runtime}",
            f"DBUS_SESSION_BUS_ADDRESS=unix:path={runtime}/bus",
            "systemctl", "--user", *args,
        ]
    else:
        cmd = ["systemctl", "--user", *args]
    return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=30)


def _port_pids() -> list[int]:
    pids: list[int] = []
    try:
        out = subprocess.check_output(
            ["ss", "-ltnp"], text=True, timeout=5, stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return pids
    for line in out.splitlines():
        if f":{PORT}" not in line:
            continue
        for m in re.finditer(r"pid=(\d+)", line):
            pids.append(int(m.group(1)))
    return pids


def _clear_orphans() -> str:
    """Stop non-systemd holders of the bridge port so the unit can bind."""
    killed: list[str] = []
    try:
        subprocess.run(
            ["pkill", "-f", "hermes-zalo-plugin/server.js"],
            check=False,
            timeout=10,
        )
        subprocess.run(
            ["pkill", "-f", "hermes-zalo-plugin start"],
            check=False,
            timeout=10,
        )
        killed.append("pkill_plugin")
    except (OSError, subprocess.TimeoutExpired):
        killed.append("pkill_fail")
    time.sleep(1)
    for pid in _port_pids():
        try:
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", "replace"
            )
        except OSError:
            continue
        if "hermes-zalo-plugin" in cmdline or "server.js" in cmdline:
            try:
                os.kill(pid, 9)
                killed.append(f"kill:{pid}")
            except OSError:
                pass
    time.sleep(1)
    return ",".join(killed) or "none"


def restart_plugin() -> str:
    """Restart the host Node bridge; prefer systemd user unit over orphans."""
    uid = _plugin_uid()
    if uid == 0:
        uid = 1000
    user = pwd.getpwuid(uid).pw_name

    # Ensure bind is reachable from Docker zalo-proxy.
    drop = Path(pwd.getpwuid(uid).pw_dir) / ".config/systemd/user/com.hermes.zaloplugin.service.d"
    try:
        drop.mkdir(parents=True, exist_ok=True)
        override = drop / "override.conf"
        body = (
            "[Service]\n"
            f"Environment=ZALO_PLUGIN_HOST={HOST_BIND}\n"
            f"Environment=ZALO_PLUGIN_PORT={PORT}\n"
        )
        # Preserve existing token/API env if present.
        existing = override.read_text(encoding="utf-8", errors="replace") if override.is_file() else ""
        if "ZALO_PLUGIN_HOST=" not in existing:
            override.write_text(
                (existing.rstrip() + "\n" if existing.strip() else "") + body,
                encoding="utf-8",
            )
        else:
            lines = []
            for line in existing.splitlines():
                if line.startswith("Environment=ZALO_PLUGIN_HOST="):
                    lines.append(f"Environment=ZALO_PLUGIN_HOST={HOST_BIND}")
                elif line.startswith("Environment=ZALO_PLUGIN_PORT="):
                    lines.append(f"Environment=ZALO_PLUGIN_PORT={PORT}")
                else:
                    lines.append(line)
            override.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if os.geteuid() == 0:
            os.chown(drop, uid, pwd.getpwuid(uid).pw_gid)
            os.chown(override, uid, pwd.getpwuid(uid).pw_gid)
    except OSError as e:
        return f"OVERRIDE_FAIL:{e}"

    cleared = _clear_orphans()
    _systemctl_user(uid, "daemon-reload")

    # Try primary unit, then assistant-zalo fallback.
    for unit in ("com.hermes.zaloplugin.service", "assistant-zalo.service"):
        listed = _systemctl_user(uid, "list-unit-files", unit)
        if listed.returncode != 0 and unit not in (listed.stdout or ""):
            # Still try restart — list-unit-files may need different args.
            pass
        r = _systemctl_user(uid, "enable", "--now", unit)
        r2 = _systemctl_user(uid, "restart", unit)
        time.sleep(2)
        # Health check
        try:
            import urllib.request

            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5) as resp:
                if resp.status == 200:
                    return (
                        f"RESTART_SYSTEMD unit={unit} uid={uid} user={user} "
                        f"cleared={cleared} enable={r.returncode} restart={r2.returncode}"
                    )
        except Exception:  # noqa: BLE001
            continue

    # Last resort: single supervised start (still not a second competing unit).
    node = shutil.which("node") or "/usr/bin/node"
    argv = [node, str(PLUGIN)]
    env = os.environ.copy()
    pw = pwd.getpwuid(uid)
    env["HOME"] = pw.pw_dir
    env["USER"] = pw.pw_name
    env["ZALO_PLUGIN_HOST"] = HOST_BIND
    env["ZALO_PLUGIN_PORT"] = PORT
    if os.geteuid() == 0:
        argv = ["runuser", "-u", user, "--"] + argv
    subprocess.Popen(
        argv,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )
    return f"RESTART_FALLBACK_POPEN uid={uid} cleared={cleared}"


def main() -> int:
    result = patch_server()
    quote_result = patch_zalo_client()
    print(f"bridge_patch={result}")
    print(f"quote_patch={quote_result}")
    need_restart = (
        result.get("status") == "WRITTEN"
        or result.get("media") == "PATCHED"
        or quote_result.get("status") == "WRITTEN"
    )
    # Always heal EADDRINUSE crash-loops when explicitly requested.
    force = (os.environ.get("ZALO_BRIDGE_FORCE_RESTART") or "").strip() in {
        "1",
        "true",
        "yes",
    }
    if need_restart or force:
        print(f"bridge_restart={restart_plugin()}")
    else:
        print("bridge_restart=SKIP")
    return 0 if result.get("status") in {"WRITTEN", "UNCHANGED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
