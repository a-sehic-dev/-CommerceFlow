# Build React marketing landing → static/landing/
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
$Snapshot = Join-Path $Root "data\demo_companies\watch_analytics_snapshot.json"
if (-not (Test-Path $Snapshot)) {
  Write-Host "Watch snapshot missing - running generate_watch_demo.py..."
  & $Py (Join-Path $Root "scripts\generate_watch_demo.py")
}
Set-Location (Join-Path $Root "landing")
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Write-Host "Landing built to static/landing/"
