@echo off
setlocal
set "PHASE=%~1"
if "%PHASE%"=="" set "PHASE=prepare"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0trace.ps1" -Phase "%PHASE%"
set "RESULT=%errorlevel%"
pause
exit /b %RESULT%
