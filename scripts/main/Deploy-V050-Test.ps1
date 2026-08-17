#Requires -Version 5.1
<#
.SYNOPSIS
  Deploy v0.5.0 test cycle to VPS (Low → Medium → High). No Grafana/Loki/Prometheus.
  Zalo QR remains manual.
#>
[CmdletBinding()]
param(
    [string] $HostName = $(if ($env:ASSISTANT_SSH_HOST) { $env:ASSISTANT_SSH_HOST } else { "" }),
    [string] $UserName = $(if ($env:ASSISTANT_SSH_USER) { $env:ASSISTANT_SSH_USER } else { "" }),
    [string] $Password = $(if ($env:ASSISTANT_SSH_PASSWORD) { $env:ASSISTANT_SSH_PASSWORD } else { "" })
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (-not $HostName) { throw "Set ASSISTANT_SSH_HOST or -HostName" }
if (-not $UserName) { throw "Set ASSISTANT_SSH_USER or -UserName" }
if (-not $Password) { throw "Set ASSISTANT_SSH_PASSWORD or -Password" }
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$env:ASSISTANT_SSH_HOST = $HostName
$env:ASSISTANT_SSH_USER = $UserName
$env:ASSISTANT_SSH_PASSWORD = $Password
$env:ASSISTANT_REPO_ROOT = $RepoRoot
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$py = Join-Path $PSScriptRoot "deploy_v050_vps.py"
$t = [IO.File]::ReadAllText($py).Replace("`r`n", "`n")
[IO.File]::WriteAllText($py, $t, [Text.UTF8Encoding]::new($false))
python -X utf8 $py
if ($LASTEXITCODE -ne 0) { throw "deploy_v050_vps.py exit $LASTEXITCODE" }
