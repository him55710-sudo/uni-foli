$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$uvicornPath = ".\.venv\Scripts\uvicorn.exe"
if (-not (Test-Path $uvicornPath)) {
  Write-Host "No local virtual environment found. Running setup-local in SQLite mode..."
  & "$PSScriptRoot\setup-local.ps1" sqlite
}

if (-not (Test-Path $uvicornPath)) {
  throw "Unable to find $uvicornPath even after setup."
}

& .\.venv\Scripts\uvicorn.exe polio_api.main:app --reload --host 127.0.0.1 --port 8000
