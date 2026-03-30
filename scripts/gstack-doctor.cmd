@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0gstack-doctor.ps1" %*
endlocal
