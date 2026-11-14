@echo off
setlocal
set "PHASE=%~1"
if "%PHASE%"=="" set "PHASE=install"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" -Phase "%PHASE%"
exit /b %errorlevel%
