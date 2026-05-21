# CommerceFlow — clean start (Windows)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$port = if ($env:CF_PORT) { $env:CF_PORT } else { "8000" }

Write-Host "Stopping old processes on port $port..."
Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "ERROR: .venv not found. Run: python -m venv .venv && .\.venv\Scripts\pip install -r requirements.txt"
    exit 1
}

$env:CF_HOST = "127.0.0.1"
$env:CF_PORT = $port

Write-Host ""
Write-Host "CommerceFlow starting at http://127.0.0.1:$port"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

& $py run.py
