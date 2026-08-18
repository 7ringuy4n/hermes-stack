#Requires -Version 5.1
<#
.SYNOPSIS
  Sync Zalo heal scripts to VPS (LF-safe). Optional remote heal.

.EXAMPLE
  $env:ASSISTANT_SSH_HOST='<host>'
  $env:ASSISTANT_SSH_USER='<user>'
  $env:ASSISTANT_SSH_PASSWORD='<password>'
  pwsh -File scripts/main/Apply-ZaloHeal.ps1 -RunHeal
#>
[CmdletBinding()]
param(
    [string] $HostName = $(if ($env:ASSISTANT_SSH_HOST) { $env:ASSISTANT_SSH_HOST } else { "" }),
    [string] $UserName = $(if ($env:ASSISTANT_SSH_USER) { $env:ASSISTANT_SSH_USER } else { "" }),
    [string] $Password = $(if ($env:ASSISTANT_SSH_PASSWORD) { $env:ASSISTANT_SSH_PASSWORD } else { "" }),
    [switch] $RunHeal
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if (-not $HostName -or -not $UserName -or -not $Password) {
    throw "Set -HostName/-UserName/-Password or ASSISTANT_SSH_* env vars (do not commit secrets)."
}

$env:ASSISTANT_REPO_ROOT = $RepoRoot
$env:ASSISTANT_SSH_HOST = $HostName
$env:ASSISTANT_SSH_USER = $UserName
$env:ASSISTANT_SSH_PASSWORD = $Password
$env:ASSISTANT_RUN_HEAL = $(if ($RunHeal) { "1" } else { "0" })

$tmpPy = Join-Path ([System.IO.Path]::GetTempPath()) ("apply_zalo_heal_{0}.py" -f [guid]::NewGuid().ToString("N"))
$py = @'
import os
import paramiko
from pathlib import Path

host = os.environ["ASSISTANT_SSH_HOST"]
user = os.environ["ASSISTANT_SSH_USER"]
pw = os.environ["ASSISTANT_SSH_PASSWORD"]
root = Path(os.environ["ASSISTANT_REPO_ROOT"])
run_heal = os.environ.get("ASSISTANT_RUN_HEAL") == "1"
files = [
    ("scripts/main/heal-zalo-sse.sh", "/opt/assistant/scripts/main/heal-zalo-sse.sh", 0o755),
    ("scripts/main/zalo-watch.sh", "/opt/assistant/scripts/main/zalo-watch.sh", 0o755),
    ("scripts/main/README-zalo-heal.md", "/opt/assistant/scripts/main/README-zalo-heal.md", 0o644),
    ("architect/backup-restore/lib/backup.sh", "/opt/assistant/architect/backup-restore/lib/backup.sh", 0o644),
]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username=user, password=pw, timeout=30)
sftp = c.open_sftp()
esc = pw.replace("'", "'\\''")
for rel, remote, mode in files:
    local = root / rel
    if not local.is_file():
        print("skip missing", rel)
        continue
    data = local.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
    tmp = "/tmp/" + Path(remote).name
    with sftp.file(tmp, "wb") as f:
        f.write(data)
    _, o, e = c.exec_command(
        f"echo '{esc}' | sudo -S install -m {mode:o} {tmp} {remote}", timeout=60
    )
    out = (o.read() + e.read()).decode("utf-8", "replace")
    if out.strip():
        print(out[-400:])
    print("installed", remote)
sftp.close()
if run_heal:
    _, o, e = c.exec_command(
        f"echo '{esc}' | sudo -S bash -lc 'ENABLE_ZALO=1 bash /opt/assistant/scripts/main/heal-zalo-sse.sh'",
        timeout=180,
    )
    print((o.read() + e.read()).decode("utf-8", "replace"))
c.close()
print("Apply-ZaloHeal done")
'@
[System.IO.File]::WriteAllText($tmpPy, ($py -replace "`r`n", "`n"), [System.Text.UTF8Encoding]::new($false))
try {
    python $tmpPy
    if ($LASTEXITCODE -ne 0) { throw "apply_zalo_heal.py exit $LASTEXITCODE" }
}
finally {
    Remove-Item -LiteralPath $tmpPy -Force -ErrorAction SilentlyContinue
}
