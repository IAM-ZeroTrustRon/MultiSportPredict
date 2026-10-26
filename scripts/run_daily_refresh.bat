@echo off
REM ===================================================================
REM  MultiSportPredict - daily all-sport refresh (Task Scheduler entry)
REM
REM  Runs the supported entrypoint once and writes a timestamped log.
REM  Exit code is propagated so Task Scheduler can report LastTaskResult.
REM  This replaces the drifted task that only ran ingest_soccer.py.
REM ===================================================================
setlocal
cd /d "%~dp0.."

set "PY=%~dp0..\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
if not exist "logs" mkdir "logs"

set "STAMP=manual"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss" 2^>nul') do set "STAMP=%%I"

set "LOG=logs\daily_refresh_%STAMP%.log"
echo [%DATE% %TIME%] starting daily refresh >> "%LOG%"

"%PY%" -u msp.py daily --all >> "%LOG%" 2>&1
set "CODE=%ERRORLEVEL%"

echo [%DATE% %TIME%] daily refresh finished exit=%CODE% >> "%LOG%"
echo [%DATE% %TIME%] daily_refresh exit=%CODE% log=%LOG% >> "logs\automation_status.log"

exit /b %CODE%
