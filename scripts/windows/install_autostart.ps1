$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\\..")
$runner = Join-Path $repoRoot "scripts\\windows\\run_bridge.cmd"

if (-not (Test-Path $runner)) {
  throw "Runner not found: $runner"
}

$startupDir = [Environment]::GetFolderPath("Startup")
$vbsPath = Join-Path $startupDir "discord-telegram-bridge.vbs"

$vbs = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run Chr(34) & "$runner" & Chr(34), 0
Set WshShell = Nothing
"@

Set-Content -LiteralPath $vbsPath -Value $vbs -Encoding ASCII
Write-Host "Installed autostart: $vbsPath"

Write-Host "You can run it now with:"
Write-Host "  wscript `"$vbsPath`""

