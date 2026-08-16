# Apply-EdgeUpdate.ps1
# Pack edge/gateway files and optionally apply on a remote host via single-line SSH.
# Does NOT deploy unless -RemoteHost is set AND -ConfirmApply is passed (permission gate).
# UTF-8 safe; strips CR from remote bash; fails on non-zero exit.
#
# Examples:
#   .\scripts\main\Apply-EdgeUpdate.ps1 -PackOnly
#   .\scripts\main\Apply-EdgeUpdate.ps1 -RemoteHost tringuyen@HOST -RemoteRoot /opt/assistant -ConfirmApply

[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$RemoteHost = "",
    [string]$RemoteRoot = "/opt/assistant",
    [switch]$PackOnly,
    [switch]$ConfirmApply,
    [switch]$SkipSudo
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-Step([string]$msg) { Write-Host "==> $msg" }

function Assert-ExitOk {
    param([int]$Code, [string]$What)
    if ($Code -ne 0) { throw "FAILED ($Code): $What" }
}

Write-Step "sources"
Write-Host "  repo:   $RepoRoot"
Write-Host "  remote: $RemoteHost $RemoteRoot"

$required = @(
    "docker-compose.edge.yml",
    "architect\gateway\api-gateway\app.py",
    "architect\edge\traefik\traefik.yml",
    "docs\05-edge-networking.md"
)
foreach ($rel in $required) {
    $p = Join-Path $RepoRoot $rel
    if (-not (Test-Path -LiteralPath $p)) { throw "Missing: $p" }
}

$tar = Join-Path $env:TEMP "nh-edge-stubs.tar"
if (Test-Path $tar) { Remove-Item -Force $tar }

Write-Step "pack $tar"
Push-Location $RepoRoot
try {
    # Prefer tar (Windows 10+); fail clearly if missing
    & tar -cf $tar `
        docker-compose.edge.yml `
        architect/gateway `
        architect/edge `
        architect/backup-restore/lib/profile.sh `
        run.sh `
        docs/05-edge-networking.md `
        docs/config/DEFAULTS.md `
        docs/config/edge.env.snippet `
        .env.example
    Assert-ExitOk $LASTEXITCODE "tar pack"
}
finally { Pop-Location }

if ($PackOnly -or [string]::IsNullOrWhiteSpace($RemoteHost)) {
    Write-Host "Packed only: $tar"
    Write-Host "To apply remotely, re-run with -RemoteHost USER@HOST -ConfirmApply (explicit permission)."
    exit 0
}

if (-not $ConfirmApply) {
    throw "Refusing remote apply without -ConfirmApply (no VPS deploy without permission)."
}

$sudo = if ($SkipSudo) { "" } else { "sudo " }
# Single-line remote script — avoid PowerShell here-string CRLF breaking bash (/tmp\r)
$remoteCmd = "set -euo pipefail; $sudo mkdir -p '$RemoteRoot'; $sudo tar -xf /tmp/nh-edge-stubs.tar -C '$RemoteRoot'; $sudo sed -i 's/\r$//' '$RemoteRoot/run.sh' '$RemoteRoot/architect/backup-restore/lib/profile.sh' 2>/dev/null || true; echo OK:edge-files-extracted"

Write-Step "scp -> ${RemoteHost}:/tmp/nh-edge-stubs.tar"
& scp $tar "${RemoteHost}:/tmp/nh-edge-stubs.tar"
Assert-ExitOk $LASTEXITCODE "scp"

Write-Step "ssh apply (sudo for extract)"
& ssh -t $RemoteHost $remoteCmd
Assert-ExitOk $LASTEXITCODE "ssh apply"

Write-Host "Done. On host: edit .env flags, then: bash run.sh up"
Write-Host "Verify: curl -sf http://127.0.0.1:8088/health"
