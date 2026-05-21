# Run any git command from the CommerceFlow project root (never from C:\Users\User).
# Usage: .\scripts\git-here.ps1 status
#        .\scripts\git-here.ps1 push -u origin main
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$GitArgs
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path (Join-Path $Root ".git"))) {
    Write-Host "ERROR: No .git in $Root — run git init here first." -ForegroundColor Red
    exit 1
}

Write-Host "Git root: $Root" -ForegroundColor DarkGray
& git @GitArgs
