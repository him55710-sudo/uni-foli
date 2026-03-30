Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

python -m pytest `
  backend/tests/test_security_hardening.py `
  backend/tests/test_auth_and_diagnosis_runtime.py `
  backend/tests/test_ingest_and_render.py `
  -q
