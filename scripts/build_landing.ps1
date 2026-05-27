# Build React marketing landing → static/landing/
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
$Snapshot = Join-Path $Root "data\demo_companies\atlas_analytics_snapshot.json"
if (-not (Test-Path $Snapshot)) {
  Write-Host "Atlas snapshot missing - running generate_atlas_demo.py (syncs landing preview)..."
  & $Py (Join-Path $Root "scripts\generate_atlas_demo.py")
}
Set-Location (Join-Path $Root "landing")
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Write-Host "Landing built to static/landing/"
