param(
  [ValidateSet("sqlite", "postgres")]
  [string]$DatabaseMode = "sqlite"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$venvPython = ".\.venv\Scripts\python.exe"
$shouldCreateVenv = $false

if (Test-Path ".venv") {
  if (-not (Test-Path $venvPython)) {
    Write-Host "Broken .venv detected. Recreating virtual environment..."
    Remove-Item ".venv" -Recurse -Force
    $shouldCreateVenv = $true
  }
} else {
  $shouldCreateVenv = $true
}

if ($shouldCreateVenv) {
  python -m venv .venv
}

if (-not (Test-Path $venvPython)) {
  throw "Unable to find $venvPython."
}

& $venvPython -m ensurepip --upgrade
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -e .[dev]

if (-not (Test-Path ".env")) {
  if ($DatabaseMode -eq "postgres") {
    Copy-Item .env.example .env
  } else {
    Copy-Item .env.sqlite.example .env
  }
}

Write-Host "Local setup complete."
if ($DatabaseMode -eq "postgres") {
  Write-Host "PostgreSQL mode selected. Run infra + migration before starting API:"
  Write-Host "  .\\scripts\\start-infra.cmd"
  Write-Host "  .\\scripts\\migrate.cmd"
} else {
  Write-Host "SQLite mode selected. You can start API immediately:"
  Write-Host "  .\\scripts\\start-api.cmd"
}
