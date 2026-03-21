$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
& .\.venv\Scripts\uvicorn.exe polio_api.main:app --reload --host 127.0.0.1 --port 8000
