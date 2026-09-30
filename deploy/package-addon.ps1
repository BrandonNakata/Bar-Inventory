<#
  Build the React app and copy the Home Assistant add-on to the Pi over Samba.

      .\deploy\package-addon.ps1 -HaHost <pi-address> [-WithDatabase] [-SkipBuild]
#>

param(
  # The Pi's address or hostname.
  [string]$HaHost = "homeassistant.local",

  # \\<host>\addons is the Samba add-on's share.
  [string]$Destination = "\\$HaHost\addons\bar_inventory",

  # Also copy backend\bar.db to the share for the add-on's first-start import.
  [switch]$WithDatabase,

  # Reuse the existing frontend\dist instead of rebuilding it.
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

# Resolve paths from the script's folder, not the working directory.
$root = Split-Path -Parent $PSScriptRoot

$parent = Split-Path -Parent $Destination
if (-not (Test-Path $parent)) {
  throw "Can't see $parent. Is Home Assistant's Samba share add-on running, and have you opened \\$HaHost in File Explorer once (so Windows has your login)?"
}

# --- 1. Build the frontend ------------------------------------------------
if (-not $SkipBuild) {
  Write-Host "Building the frontend..." -ForegroundColor Cyan
  Push-Location "$root\frontend"
  try {
    npm run build
    # npm failures don't throw in PowerShell, so check the exit code.
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed (see above)" }
  }
  finally { Pop-Location }
}
if (-not (Test-Path "$root\frontend\dist\index.html")) {
  throw "No frontend\dist\index.html -- run without -SkipBuild."
}

# --- 2. Copy the add-on folder ---------------------------------------------
Write-Host "Copying to $Destination ..." -ForegroundColor Cyan

# Clear old code so deleted files don't linger in the add-on.
foreach ($sub in "backend", "static") {
  $old = "$Destination\$sub"
  if (Test-Path $old) {
    Remove-Item $old -Recurse -Force
    # Samba deletes can lag; wait up to 10 seconds.
    $waited = 0
    while ((Test-Path $old) -and $waited -lt 20) {
      Start-Sleep -Milliseconds 500
      $waited++
    }
  }
}

# Create folders, then copy contents with -Force; avoids Copy-Item nesting and Samba lag errors.
foreach ($dir in "backend\app", "static") {
  New-Item -ItemType Directory -Force "$Destination\$dir" | Out-Null
}

Copy-Item "$root\deploy\ha-addon\*" $Destination -Force
Copy-Item "$root\backend\requirements.txt" "$Destination\backend\" -Force
Copy-Item "$root\backend\app\*" "$Destination\backend\app" -Recurse -Force
Copy-Item "$root\frontend\dist\*" "$Destination\static" -Recurse -Force

# Drop bytecode built for the local Python.
Get-ChildItem "$Destination\backend" -Recurse -Directory -Filter "__pycache__" |
  Remove-Item -Recurse -Force

# --- 3. Optionally, the database -------------------------------------------
if ($WithDatabase) {
  $share = "\\$HaHost\share\bar_inventory"
  New-Item -ItemType Directory -Force $share | Out-Null
  Copy-Item "$root\backend\bar.db" "$share\bar.db" -Force
  Write-Host "Copied bar.db to $share (used on the add-on's first start only)." -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Done. In Home Assistant: Settings > Add-ons > Bar Inventory > Rebuild" -ForegroundColor Green
Write-Host "(first time: Add-on store > three-dot menu > Check for updates, then install it from Local add-ons)"
