$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot\..
& .\.venv\Scripts\alembic.exe upgrade head

Write-Host "Alembic migration complete."
