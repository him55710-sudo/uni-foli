@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-worker.ps1" %*
endlocal
