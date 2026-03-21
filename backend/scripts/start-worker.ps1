$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$pythonPath = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
  Write-Host "No local virtual environment found. Running setup-local in SQLite mode..."
  & "$PSScriptRoot\setup-local.ps1" sqlite
}

if (-not (Test-Path $pythonPath)) {
  throw "Unable to find $pythonPath even after setup."
}

& .\.venv\Scripts\python.exe -m polio_worker.main run-pending
