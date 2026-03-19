$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot\..
docker compose up -d postgres valkey

Write-Host "Postgres + Valkey are starting in Docker."
