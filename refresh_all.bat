@echo off
REM ===================================================================
REM  MultiSportPredict - daily data refresh
REM  Runs every league adapter in ingest_all_sports.py and logs the run.
REM  Any argument you pass is forwarded, e.g.:
REM      refresh_all.bat --only kbo tennis
REM      refresh_all.bat --check
REM ===================================================================
setlocal
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

set "STAMP=manual"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd" 2^>nul') do set "STAMP=%%I"
set "LOG=logs\ingest_%STAMP%.log"

echo ===============================================================
echo  MultiSportPredict daily refresh - %DATE% %TIME%
echo  Python: %PY%
echo  Log:    %LOG%
echo ===============================================================

"%PY%" "%~dp0ingest_all_sports.py" %* >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"

type "%LOG%"
echo.
echo Exit code %RC%  ^(0 = every source OK, 1 = some failed, 2 = all failed^)
exit /b %RC%
