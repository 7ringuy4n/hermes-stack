#!/usr/bin/env python3
"""Idempotent: add POST /inject-event on hermes-zalo-plugin (SSE fan-out).

Lab and product tests inject a synthetic inbound message onto the same SSE
stream Hermes already consumes. Does not open a second SSE client.
Does not interpret user language — payload is a known bridge protocol object.
"""
from __future__ import annotations

import os
import pwd
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
MARKER = "POST /inject-event"
SNIPPET = r"""
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


def patch_server() -> str:
    if not PLUGIN.is_file():
        return "PLUGIN_MISSING"
    text = PLUGIN.read_text(encoding="utf-8", errors="replace")
    if MARKER in text:
        return "ALREADY"
    needle = "_httpServer = app.listen("
    idx = text.find(needle)
    if idx < 0:
        return "LISTEN_MISSING"
    PLUGIN.write_text(text[:idx] + SNIPPET + text[idx:], encoding="utf-8")
    return "PATCHED"


def _plugin_uid() -> int | None:
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "hermes-zalo-plugin/server.js"],
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    pid = (out.split() or [""])[0]
    if not pid.isdigit():
        return None
    try:
        return os.stat(f"/proc/{pid}").st_uid
    except OSError:
        return None


def restart_plugin() -> str:
    """Restart the host Node bridge without a second SSE login (cookies stay on disk)."""
    uid = _plugin_uid()
    if uid is None:
        try:
            uid = int((os.environ.get("ZALO_PLUGIN_UID") or "1000").strip())
        except ValueError:
            uid = 1000
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
    except (OSError, subprocess.TimeoutExpired):
        return "PKILL_FAIL"
    time.sleep(2)
    node = shutil.which("node") or "/usr/bin/node"
    argv = [node, str(PLUGIN)]
    if os.geteuid() == 0 and uid is not None:
        user = pwd.getpwuid(uid).pw_name
        argv = ["runuser", "-u", user, "--"] + argv
    env = os.environ.copy()
    if uid is not None:
        pw = pwd.getpwuid(uid)
        env["HOME"] = pw.pw_dir
        env["USER"] = pw.pw_name
    try:
        subprocess.Popen(
            argv,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
    except OSError:
        node = shutil.which("node") or "/usr/bin/node"
        argv2 = [node, str(PLUGIN)]
        if os.geteuid() == 0 and uid is not None:
            user = pwd.getpwuid(uid).pw_name
            argv2 = ["runuser", "-u", user, "--"] + argv2
        subprocess.Popen(
            argv2,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
    return f"RESTART_ISSUED uid={uid}"


def main() -> int:
    status = patch_server()
    print(f"inject_patch={status}")
    if status == "PATCHED":
        print(f"inject_restart={restart_plugin()}")
    elif status == "ALREADY":
        print("inject_restart=SKIP")
    return 0 if status in {"PATCHED", "ALREADY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
