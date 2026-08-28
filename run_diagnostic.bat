@echo off
REM ===================================================================
REM  DOUBLE-CLICK THIS FILE.
REM  Saves the result to diagnostic_report.txt in this same folder.
REM ===================================================================
cd /d "%~dp0" 2>nul

set "PY=venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo Running network diagnostic, please wait (about 60 seconds)...
echo.

"%PY%" diagnose_sources.py > diagnostic_report.txt 2>&1

type diagnostic_report.txt

echo.
echo ===============================================================
echo  Saved to: diagnostic_report.txt  (in this folder)
echo ===============================================================
echo.
pause
