# -*- coding: utf-8 -*-
"""Medium lab: destroy, redeploy, copy skills, post-ready-learn, probe cases 12–14.

Env: ASSISTANT_SSH_HOST, ASSISTANT_SSH_USER, ASSISTANT_SSH_PASSWORD
Optional: ASSISTANT_REPO_ROOT, SKIP_SYNC=1
Reports: test/reports/run-skills-lab/ (no host/account in output files)
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanitize import sanitize

HOST = os.environ["ASSISTANT_SSH_HOST"]
USER = os.environ["ASSISTANT_SSH_USER"]
PW = os.environ["ASSISTANT_SSH_PASSWORD"]
ROOT = Path(os.environ.get("ASSISTANT_REPO_ROOT", Path(__file__).resolve().parents[2]))
REMOTE = "/opt/assistant"
OUT = ROOT / "test" / "reports" / "run-skills-lab"
SKIP_SYNC = os.environ.get("SKIP_SYNC", "0").strip() in {"1", "true", "yes"}
SKIP_DESTROY = os.environ.get("SKIP_DESTROY", "0").strip() in {"1", "true", "yes"}
esc = PW.replace("'", "'\\''")
ROWS: list[dict] = []

SKIP_DIR = {
    ".git",
    "__pycache__",
    "node_modules",
    ".cursor",
    "hermes/temp",
    "scripts/temp",
    "test/reports",
}
TEXT_EXT = {".sh", ".py", ".yml", ".yaml", ".md", ".json", ".txt", ".example"}


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def note(name: str, status: str, detail: str = "") -> None:
    row = {"ts": ts(), "name": name, "status": status, "detail": sanitize(detail)[:800]}
    ROWS.append(row)
    print(f"[{row['ts']}] {name} | {status} | {row['detail'][:240]}", flush=True)


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PW, timeout=45, allow_agent=False, look_for_keys=False)
    return c


def _write_console(chunk: str) -> None:
    try:
        sys.stdout.write(chunk)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.write(chunk.encode(enc, errors="replace").decode(enc, errors="replace"))
    sys.stdout.flush()


def sudo_bash(c, script: str, timeout: int = 3600) -> str:
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    cmd = f"echo '{esc}' | sudo -S bash -lc \"echo {b64} | base64 -d | bash\""
    _i, o, e = c.exec_command(cmd, timeout=timeout, get_pty=True)
    chan = o.channel
    buf: list[str] = []
    while True:
        while chan.recv_ready():
            chunk = chan.recv(16384).decode("utf-8", "replace")
            _write_console(chunk)
            buf.append(chunk)
        while chan.recv_stderr_ready():
            chunk = chan.recv_stderr(16384).decode("utf-8", "replace")
            _write_console(chunk)
            buf.append(chunk)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.15)
    code = chan.recv_exit_status()
    text = sanitize("".join(buf))
    if code != 0:
        raise SystemExit(f"remote exit {code}: {text[-500:]}")
    return text


def should_skip(rel: str) -> bool:
    r = rel.replace("\\", "/")
    if any(p == "__pycache__" or p.endswith(".pyc") for p in r.split("/")):
        return True
    for s in SKIP_DIR:
        if r.startswith(s.rstrip("/") + "/") or r == s:
            return True
    return False


def _file_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_EXT or path.name in {"run.sh", "Dockerfile"}:
        try:
            data = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        except UnicodeDecodeError:
            pass
    return data


def _add_file(tar: tarfile.TarFile, path: Path, arc: str) -> None:
    data = _file_bytes(path)
    info = tarfile.TarInfo(name=arc)
    info.size = len(data)
    if path.suffix == ".sh" or path.name == "run.sh":
        info.mode = 0o755
    tar.addfile(info, io.BytesIO(data))


def pack_tree() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if should_skip(rel):
                continue
            _add_file(tar, path, rel)
    return buf.getvalue()


def pack_skills() -> tuple[bytes, list[str]]:
    """Dedicated skills archive so category folders cannot be dropped by a partial tree extract."""
    skills = ROOT / "hermes" / "main" / "skills"
    names: list[str] = []
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in skills.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if "__pycache__" in rel.split("/"):
                continue
            _add_file(tar, path, rel)
            if path.name == "SKILL.md":
                names.append(rel)
    required = "hermes/main/skills/core/answering/SKILL.md"
    if required not in names:
        raise SystemExit(f"local pack missing {required}; found {len(names)} SKILL.md")
    return buf.getvalue(), names


def sftp_put(c, local_bytes: bytes, remote_path: str) -> None:
    sftp = c.open_sftp()
    with sftp.file(remote_path, "wb") as f:
        f.write(local_bytes)
    sftp.close()


def sync_tree(c) -> None:
    note("sync", "start", "packing source + skills")
    tree = pack_tree()
    skills, skill_mds = pack_skills()
    note("sync_skills_pack", "pass", f"SKILL.md count={len(skill_mds)}")
    sftp_put(c, tree, "/tmp/assistant-sync.tgz")
    sftp_put(c, skills, "/tmp/hermes-skills.tgz")
    sudo_bash(
        c,
        f"""
set -euo pipefail
mkdir -p {REMOTE}
tar -xzf /tmp/assistant-sync.tgz -C {REMOTE}
tar -xzf /tmp/hermes-skills.tgz -C {REMOTE}
find {REMOTE} -type f \\( -name '*.sh' -o -name 'run.sh' \\) -exec sed -i 's/\\r$//' {{}} +
chmod +x {REMOTE}/run.sh || true
test -f {REMOTE}/hermes/main/skills/core/answering/SKILL.md
test -f {REMOTE}/hermes/main/skills/knowledge/knowledge-rag/SKILL.md
test -f {REMOTE}/hermes/main/skills/image-gen/SKILL.md
echo SKILLS_ON_DISK_OK
echo SYNC_OK
""",
        timeout=600,
    )
    note("sync", "pass", f"tree={len(tree)} skills={len(skills)}")


def remote_lab(c) -> str:
    skip_destroy = "1" if SKIP_DESTROY else "0"
    return sudo_bash(
        c,
        rf"""
set -euo pipefail
cd {REMOTE}
touch .env
upsert() {{
  local k="$1" v="$2"
  if grep -q "^${{k}}=" .env; then sed -i "s|^${{k}}=.*|${{k}}=${{v}}|" .env
  else echo "${{k}}=${{v}}" >> .env; fi
}}
upsert ASSISTANT_PROFILE medium
upsert ENABLE_ZALO 0
upsert ENABLE_TRAEFIK 1
upsert ENABLE_API_GATEWAY 1
upsert TRAEFIK_MODE local
upsert ENABLE_ANTIVIRUS 0
upsert SECURITY_SANDBOX 0
upsert SECURITY_LLM_JUDGE 0
upsert LEARN_REQUIRE_APPROVE 0
upsert HERMES_REPLICAS 1
grep -q '^ASSISTANT_DATA_DIR=' .env || upsert ASSISTANT_DATA_DIR /data/assistant
grep -q '^HERMES_DATA_DIR=' .env || upsert HERMES_DATA_DIR /data/assistant
grep -q '^GATEWAY_API_KEYS=' .env || upsert GATEWAY_API_KEYS "$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')"
mkdir -p /data/assistant/docs /data/assistant/backups /data/assistant/media/out
chown -R 1000:1000 /data/assistant || true

echo "=== CLEAR OLD DOCS MIRROR ==="
rm -rf /data/assistant/docs/skills /data/assistant/docs/setup /data/assistant/docs/hermes-docs 2>/dev/null || true
tar -xzf /tmp/hermes-skills.tgz -C {REMOTE}
test -f {REMOTE}/hermes/main/skills/core/answering/SKILL.md

export COMPOSE_PROGRESS=plain
if [[ "{skip_destroy}" == "1" ]]; then
  echo "=== SKIP DESTROY; rebuild embedding+ingest+dispatcher ==="
  docker rm -f ingest dispatcher embedding 2>/dev/null || true
  docker compose --project-directory {REMOTE} -f {REMOTE}/docker/docker-compose.yml build embedding dispatcher ingest
  docker compose --project-directory {REMOTE} -f {REMOTE}/docker/docker-compose.yml up -d embedding ingest dispatcher
  sleep 8
else
  echo "=== DESTROY + MEDIUM UP ==="
  bash run.sh destroy
  tar -xzf /tmp/hermes-skills.tgz -C {REMOTE}
  test -f {REMOTE}/hermes/main/skills/core/answering/SKILL.md
  docker compose --project-directory {REMOTE} -f {REMOTE}/docker/docker-compose.yml build embedding dispatcher ingest
  bash run.sh up
  sleep 20
fi

echo "=== FIRST SETUP LLM ==="
if grep -qE '^OMNIROUTER_INITIAL_PASSWORD=.+' .env; then
  bash run.sh first-setup-llm || true
else
  echo "WARN first-setup-llm skipped (OMNIROUTER_INITIAL_PASSWORD empty)"
fi

echo "=== RECREATE EMBED+INGEST (local fallback image) ==="
docker compose --project-directory {REMOTE} -f {REMOTE}/docker/docker-compose.yml up -d --force-recreate embedding ingest
sleep 6
curl -sS -m 10 http://127.0.0.1:8094/health || true
echo
curl -sS -m 60 -X POST http://127.0.0.1:8094/v1/embeddings -H 'content-type: application/json' -d '{{"input":"warmup"}}' | head -c 200 || true
echo
curl -sS -m 15 -X DELETE http://127.0.0.1:6333/collections/knowledge_chunks || true
echo

echo "=== POST-READY LEARN ==="
bash run.sh post-ready-learn

echo "=== HEALTH ==="
curl -fsS -m 10 http://127.0.0.1:20128/health || true
echo
curl -fsS -m 10 http://127.0.0.1:8099/health
echo
curl -fsS -m 10 http://127.0.0.1:8090/health
echo
curl -fsS -m 10 http://127.0.0.1:8080/health || true
echo
curl -fsS -m 10 http://127.0.0.1:29119/health || true
echo

echo "=== CASE12 MOUNT ==="
H=""
for i in $(seq 1 30); do
  H=$(docker ps --format '{{{{.Names}}}}' | grep -i hermes | head -1 || true)
  if [[ -n "$H" ]]; then break; fi
  sleep 2
done
test -n "$H"
docker exec "$H" test -f /opt/data/skills/core/answering/SKILL.md
docker exec "$H" test -f /opt/data/skills/image-gen/SKILL.md
docker exec "$H" test -f /opt/data/skills/knowledge/knowledge-rag/SKILL.md
echo MOUNT_OK hermes=$H

echo "=== CASE12 LEARN LIST ==="
python3 - <<'PY'
import json, urllib.request, urllib.error

def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())

def post(url, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={{"content-type": "application/json"}})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {{"ok": False, "error": e.read().decode()[:300], "code": e.code}}

pending = get("http://127.0.0.1:8099/v1/learn/pending")
print("PENDING", pending.get("count"))
ok_n = 0
fail_n = 0
for it in pending.get("items") or []:
    pid = it.get("pending_id")
    row = post("http://127.0.0.1:8099/v1/learn/approve", {{"selector": pid, "pending_id": pid}})
    if row.get("ok"):
        ok_n += 1
    else:
        fail_n += 1
        print("APPROVE_FAIL", pid, row.get("error") or row.get("code"))
print(f"APPROVE ok={{ok_n}} fail={{fail_n}}")

alld = get("http://127.0.0.1:8099/v1/learn/list?limit=5")
print(f"LEARN_LIST_ALL count={{alld.get('count')}} shown={{len(alld.get('documents') or [])}}")
hits = False
for q in ("image-gen", "knowledge-rag", "answering", "text-poster", "confidential"):
    d = get(f"http://127.0.0.1:8099/v1/learn/list?q={{q}}&limit=5")
    n = int(d.get("count") or 0)
    print(f"LEARN_LIST q={{q}} count={{n}} shown={{len(d.get('documents') or [])}}")
    if n >= 1:
        hits = True
if int(alld.get("count") or 0) < 1 and not hits:
    print("LEARN_LIST_FAIL empty catalog after approve")
else:
    print("LEARN_LIST_OK")
PY

echo "=== CASE13 TEXT POSTER ==="
set +e
python3 - <<'PY'
import json, urllib.request
body = json.dumps({{
    "prompt": 'create a black and white image, fill in 10 lines "SAMPLE TEXT"',
    "filename": "lab-text-poster.png",
    "refine": False,
}}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8090/v1/image",
    data=body,
    method="POST",
    headers={{"content-type": "application/json"}},
)
with urllib.request.urlopen(req, timeout=60) as r:
    data = json.loads(r.read().decode())
print(json.dumps(data))
if not data.get("ok") or data.get("backend") != "text-poster":
    raise SystemExit("expected backend text-poster")
if int(data.get("n") or 0) != 10 or data.get("phrase") != "SAMPLE TEXT":
    raise SystemExit("n/phrase mismatch")
print("POSTER_JSON_OK")
PY
docker exec dispatcher test -s /data/media/out/lab-text-poster.png && echo POSTER_FILE_OK
set -e

echo "=== CASE13 FAIL EMPTY PROMPT ==="
set +e
python3 - <<'PY'
import json, urllib.request, urllib.error
body = json.dumps({{"prompt": "", "refine": False}}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8090/v1/image",
    data=body,
    method="POST",
    headers={{"content-type": "application/json"}},
)
try:
    urllib.request.urlopen(req, timeout=15)
    raise SystemExit("empty prompt should fail")
except urllib.error.HTTPError as e:
    print(f"HTTP_{{e.code}}")
    if e.code != 400:
        raise SystemExit(f"expected 400 got {{e.code}}")
PY
set -e

echo "=== CASE14 KNOWLEDGE SKILLS ON MOUNT ==="
docker exec "$H" grep -qi confidential /opt/data/skills/knowledge/knowledge-rag/SKILL.md
docker exec "$H" grep -qi 'open web' /opt/data/skills/knowledge/web-search/SKILL.md
docker exec "$H" test -f /opt/data/skills/knowledge/research/SKILL.md
echo KNOWLEDGE_SKILL_OK

echo SKILLS_LAB_DONE
""",
        timeout=5400,
    )


def write_report(text: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in ROWS if r["status"] == "pass")
    failed = sum(1 for r in ROWS if r["status"] == "fail")
    summary = OUT / "SUMMARY.md"
    lines = [
        "# Skills lab (Medium)",
        "",
        f"- Timestamp: `{ts()}`",
        f"- Steps recorded: {len(ROWS)} (pass={passed}, fail={failed})",
        "",
        "## Results",
        "",
        "<table>",
        "<thead><tr><th>Step</th><th>Status</th><th>Detail</th></tr></thead>",
        "<tbody>",
    ]
    for r in ROWS:
        lines.append(
            f"<tr><td>{r['name']}</td><td>{r['status']}</td><td>{r['detail'][:200]}</td></tr>"
        )
    lines.extend(["</tbody>", "</table>", ""])
    summary.write_text("\n".join(lines), encoding="utf-8")
    (OUT / "remote.log").write_text(sanitize(text)[-120000:], encoding="utf-8")
    (OUT / "rows.json").write_text(json.dumps(ROWS, indent=2), encoding="utf-8")
    note("report", "pass", "wrote SUMMARY.md")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    c = connect()
    try:
        if not SKIP_SYNC:
            sync_tree(c)
        else:
            note("sync", "skip", "SKIP_SYNC=1")
        out = remote_lab(c)
        if "SKILLS_LAB_DONE" not in out:
            note("remote", "fail", "missing SKILLS_LAB_DONE marker")
            write_report(out)
            return 1
        for marker, name in [
            ("MOUNT_OK", "case12_mount"),
            ("LEARN_LIST_OK", "case12_learn"),
            ("POSTER_JSON_OK", "case13_poster_json"),
            ("POSTER_FILE_OK", "case13_poster"),
            ("HTTP_400", "case13_fail_empty"),
            ("KNOWLEDGE_SKILL_OK", "case14_knowledge"),
        ]:
            if marker in out:
                note(name, "pass", marker)
            else:
                note(name, "fail", f"missing {marker}")
        if SKIP_SYNC:
            note("skills_on_disk", "skip", "SKIP_SYNC=1")
        elif "SKILLS_ON_DISK_OK" in out:
            note("skills_on_disk", "pass", "SKILLS_ON_DISK_OK")
        else:
            note("skills_on_disk", "fail", "missing SKILLS_ON_DISK_OK")
        write_report(out)
        fails = [r for r in ROWS if r["status"] == "fail"]
        return 1 if fails else 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
