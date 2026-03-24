$ErrorActionPreference = "Stop"
Write-Warning "migrate-admissions.ps1 is deprecated. Forwarding to backend/scripts/migrate.ps1."
& "$PSScriptRoot\..\backend\scripts\migrate.ps1" @args
