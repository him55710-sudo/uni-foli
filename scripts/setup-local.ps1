$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot\..

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -e .[dev]

if (-not (Test-Path ".env")) {
  Copy-Item .env.example .env
}

Write-Host "Local setup complete."
Write-Host "If you want PostgreSQL + pgvector, run:"
Write-Host "  .\\scripts\\start-infra.ps1"
Write-Host "  .\\scripts\\migrate.ps1"
