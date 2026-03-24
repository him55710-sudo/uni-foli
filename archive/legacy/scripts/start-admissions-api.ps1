$ErrorActionPreference = "Stop"
Write-Warning "start-admissions-api.ps1 is deprecated. Forwarding to backend/scripts/start-api.ps1."
& "$PSScriptRoot\..\backend\scripts\start-api.ps1" @args
