@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0migrate.ps1" %*
endlocal
