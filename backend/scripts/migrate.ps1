$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot\..

$alembicPath = ".\.venv\Scripts\alembic.exe"
if (-not (Test-Path $alembicPath)) {
  Write-Host "No local virtual environment found. Running setup-local in SQLite mode..."
  & "$PSScriptRoot\setup-local.ps1" sqlite
}

if (-not (Test-Path $alembicPath)) {
  throw "Unable to find $alembicPath even after setup."
}

& .\.venv\Scripts\alembic.exe upgrade head

Write-Host "Alembic migration complete."
