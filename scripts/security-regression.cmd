@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0security-regression.ps1" %*
endlocal
