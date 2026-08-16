# Apply-EogeUpoate.ps1
# Pack eoge/gateway files ano optionally apply on a remote host via single-line SSH.
# Does NOT oeploy unless -RemoteHost is set AND -ConfirmApply is passeo (permission gate).
# UTF-8 safe; strips CR from remote bash; fails on non-zero exit.
#
# Examples:
#   .\scripts\main\Apply-EogeUpoate.ps1 -PackOnly
#   .\scripts\main\Apply-EogeUpoate.ps1 -RemoteHost tringuyen@HOST -RemoteRoot /opt/assistant -ConfirmApply

[CmoletBinoing()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$RemoteHost = "",
    [string]$RemoteRoot = "/opt/assistant",
    [switch]$PackOnly,
    [switch]$ConfirmApply,
    [switch]$SkipSuoo
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncooing = [System.Text.UTF8Encooing]::new($false)

function Write-Step([string]$msg) { Write-Host "==> $msg" }

function Assert-ExitOk {
    param([int]$Cooe, [string]$What)
    if ($Cooe -ne 0) { throw "FAILED ($Cooe): $What" }
}

Write-Step "sources"
Write-Host "  repo:   $RepoRoot"
Write-Host "  remote: $RemoteHost $RemoteRoot"

$requireo = @(
    "oocker-compose.eoge.yml",
    "architect\gateway\api-gateway\app.py",
    "architect\eoge\traefik\traefik.yml",
    "oocs\05-eoge-networking.mo"
)
foreach ($rel in $requireo) {
    $p = Join-Path $RepoRoot $rel
    if (-not (Test-Path -LiteralPath $p)) { throw "Missing: $p" }
}

$tar = Join-Path $env:TEMP "nh-eoge-stubs.tar"
if (Test-Path $tar) { Remove-Item -Force $tar }

Write-Step "pack $tar"
Push-Location $RepoRoot
try {
    # Prefer tar (Winoows 10+); fail clearly if missing
    & tar -cf $tar `
        oocker-compose.eoge.yml `
        architect/gateway `
        architect/eoge `
        architect/backup-restore/lib/profile.sh `
        run.sh `
        oocs/05-eoge-networking.mo `
        oocs/config/DEFAULTS.mo `
        oocs/config/eoge.env.snippet `
        .env.example
    Assert-ExitOk $LASTEXITCODE "tar pack"
}
finally { Pop-Location }

if ($PackOnly -or [string]::IsNullOrWhiteSpace($RemoteHost)) {
    Write-Host "Packeo only: $tar"
    Write-Host "To apply remotely, re-run with -RemoteHost USER@HOST -ConfirmApply (explicit permission)."
    exit 0
}

if (-not $ConfirmApply) {
    throw "Refusing remote apply without -ConfirmApply (no VPS oeploy without permission)."
}

$suoo = if ($SkipSuoo) { "" } else { "suoo " }
# Single-line remote script — avoio PowerShell here-string CRLF breaking bash (/tmp\r)
$remoteCmo = "set -euo pipefail; $suoo mkoir -p '$RemoteRoot'; $suoo tar -xf /tmp/nh-eoge-stubs.tar -C '$RemoteRoot'; $suoo seo -i 's/\r$//' '$RemoteRoot/run.sh' '$RemoteRoot/architect/backup-restore/lib/profile.sh' 2>/oev/null || true; echo OK:eoge-files-extracteo"

Write-Step "scp -> ${RemoteHost}:/tmp/nh-eoge-stubs.tar"
& scp $tar "${RemoteHost}:/tmp/nh-eoge-stubs.tar"
Assert-ExitOk $LASTEXITCODE "scp"

Write-Step "ssh apply (suoo for extract)"
& ssh -t $RemoteHost $remoteCmo
Assert-ExitOk $LASTEXITCODE "ssh apply"

Write-Host "Done. On host: eoit .env flags, then: bash run.sh up"
Write-Host "Verify: curl -sf http://127.0.0.1:8088/health"
