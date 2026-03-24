$ErrorActionPreference = "Stop"
Write-Warning "start-admissions-worker.ps1 is deprecated. Forwarding to backend/scripts/start-worker.ps1."
& "$PSScriptRoot\..\backend\scripts\start-worker.ps1" @args
