$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
& .\.venv\Scripts\python.exe -m polio_worker.main run-pending
