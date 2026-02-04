$ErrorActionPreference = "Stop"

$startupDir = [Environment]::GetFolderPath("Startup")
$vbsPath = Join-Path $startupDir "discord-telegram-bridge.vbs"

if (Test-Path $vbsPath) {
  Remove-Item -LiteralPath $vbsPath -Force
  Write-Host "Removed autostart: $vbsPath"
} else {
  Write-Host "Autostart not installed: $vbsPath"
}

