@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0gstack-refresh.ps1" %*
endlocal
