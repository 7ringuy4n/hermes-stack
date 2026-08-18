#Requires -Version 5.1
<#
.SYNOPSIS
  Orchestrate High-profile VPS redeploy (no Grafana/Loki/Prometheus). Avoids full-buffer hung by calling Python for SSH.

.DESCRIPTION
  Follows docs/AGENT_RULES.md. Requires explicit operator intent (you are running this).
  Does NOT open GitHub MRs. QR login for Zalo is left manual.

.EXAMPLE
  pwsh -File scripts/main/Deploy-High.ps1 -Phase destroy
  pwsh -File scripts/main/Deploy-High.ps1 -Phase sync
  pwsh -File scripts/main/Deploy-High.ps1 -Phase up
  pwsh -File scripts/main/Deploy-High.ps1 -Phase zalo-bridge
  # Then run login-zalo QR manually on VPS
  pwsh -File scripts/main/Deploy-High.ps1 -Phase verify
  pwsh -File scripts/main/Deploy-High.ps1 -Phase smoke
#>
[CmdletBinding()]
param(
    [ValidateSet("all", "destroy", "sync", "up", "zalo-bridge", "verify", "smoke", "credentials")]
    [string] $Phase = "all",
    [string] $HostName = $(if ($env:ASSISTANT_SSH_HOST) { $env:ASSISTANT_SSH_HOST } else { "" }),
    [string] $UserName = $(if ($env:ASSISTANT_SSH_USER) { $env:ASSISTANT_SSH_USER } else { "" }),
    [string] $Password = $(if ($env:ASSISTANT_SSH_PASSWORD) { $env:ASSISTANT_SSH_PASSWORD } else { "" })
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Py = Join-Path $PSScriptRoot "deploy_high_vps.py"

if (-not (Test-Path -LiteralPath $Py)) {
    throw "Missing $Py"
}
if (-not $HostName -or -not $UserName -or -not $Password) {
    throw "Set -HostName/-UserName/-Password or ASSISTANT_SSH_HOST/USER/PASSWORD (no lab defaults in source)."
}

$env:ASSISTANT_SSH_HOST = $HostName
$env:ASSISTANT_SSH_USER = $UserName
$env:ASSISTANT_SSH_PASSWORD = $Password
$env:ASSISTANT_REPO_ROOT = $RepoRoot

Write-Host "Deploy-High phase=$Phase host=$UserName@$HostName"
# Stream python output line-by-line (reduces PowerShell buffer hang risk)
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "python"
$psi.Arguments = "`"$Py`" --phase $Phase"
$psi.WorkingDirectory = $RepoRoot
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
$p = [System.Diagnostics.Process]::Start($psi)
while (-not $p.HasExited) {
    while (-not $p.StandardOutput.EndOfStream) {
        $line = $p.StandardOutput.ReadLine()
        if ($null -ne $line) { Write-Host $line }
    }
    Start-Sleep -Milliseconds 100
}
$err = $p.StandardError.ReadToEnd()
$out = $p.StandardOutput.ReadToEnd()
if ($out) { Write-Host $out }
if ($err) { Write-Host $err }
if ($p.ExitCode -ne 0) {
    throw "deploy_high_vps.py failed with exit $($p.ExitCode)"
}
