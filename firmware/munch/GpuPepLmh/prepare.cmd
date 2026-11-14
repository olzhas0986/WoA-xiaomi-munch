@echo off
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0test.ps1" -Phase prepare
set "RESULT=%errorlevel%"
pause
exit /b %RESULT%
