@echo off
REM ===================================================================
REM  MultiSportPredict - automated grading pass (Task Scheduler entry)
REM
REM  Settles saved selections against verified results for every sport.
REM  Each pass writes a full database backup under output\workflow\grade_*
REM  (that behaviour lives in msp_workflow.grade_all and is not changed
REM  here), so this wrapper only adds timestamped logging and exit codes.
REM ===================================================================
setlocal
cd /d "%~dp0.."

set "PY=%~dp0..\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
if not exist "logs" mkdir "logs"

set "STAMP=manual"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss" 2^>nul') do set "STAMP=%%I"

set "LOG=logs\hourly_grading_%STAMP%.log"
echo [%DATE% %TIME%] starting grading pass >> "%LOG%"

"%PY%" -u msp.py grade --all >> "%LOG%" 2>&1
set "CODE=%ERRORLEVEL%"

REM Rotate only the routine grade_* snapshots this task creates (keeps 72).
REM Milestone backups (refresh_*, manual copies) are never touched, and a
REM prune failure must not fail the grading pass.
"%PY%" -u scripts\prune_backups.py --keep 72 >> "%LOG%" 2>&1

echo [%DATE% %TIME%] grading finished exit=%CODE% >> "%LOG%"
echo [%DATE% %TIME%] hourly_grading exit=%CODE% log=%LOG% >> "logs\automation_status.log"

exit /b %CODE%
