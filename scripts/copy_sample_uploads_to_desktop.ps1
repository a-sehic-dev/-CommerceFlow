# Copy sample XLSX packs to Desktop for manual Browse Files testing
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Src = Join-Path $Root "data\demo_companies"
$Dest = Join-Path ([Environment]::GetFolderPath("Desktop")) "CommerceFlow-Sample-Uploads"

New-Item -ItemType Directory -Force -Path $Dest | Out-Null

$files = @(
    "watch_products.xlsx", "watch_inventory.xlsx", "watch_sales_2025.xlsx",
    "motor_products.xlsx", "motor_inventory.xlsx", "motor_sales_2025.xlsx",
    "home_products.xlsx", "home_inventory.xlsx", "home_sales_2025.xlsx"
)

foreach ($f in $files) {
    $p = Join-Path $Src $f
    if (Test-Path $p) {
        Copy-Item $p (Join-Path $Dest $f) -Force
        Write-Host "Copied $f"
    }
}

@"
CommerceFlow — sample files for manual import (Browse Files)

Upload ONE file at a time on /imports:
  1. watch_sales_2025.xlsx   -> type: Sales (or Auto-detect)
  2. watch_products.xlsx     -> Products
  3. watch_inventory.xlsx    -> Inventory
  Then Run Your Analysis and pick those three imports.

Repeat for motor_* and home_* to test other workspaces.

Quick-load buttons in the app do the same import server-side.
"@ | Set-Content (Join-Path $Dest "README.txt") -Encoding UTF8

Write-Host "`nDone -> $Dest"
