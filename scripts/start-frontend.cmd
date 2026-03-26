@echo off
setlocal
pushd "%~dp0..\frontend"
npm run dev
set _exitcode=%errorlevel%
popd
exit /b %_exitcode%
