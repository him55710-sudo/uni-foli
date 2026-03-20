@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-infra.ps1" %*
endlocal
