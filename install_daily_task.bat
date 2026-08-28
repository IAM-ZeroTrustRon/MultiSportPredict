@echo off
REM ===================================================================
REM  Double-click this file to schedule the daily data refresh.
REM  If it fails, right-click it and choose "Run as administrator".
REM ===================================================================
setlocal
set "TASKNAME=MultiSportPredict Daily Refresh"
set "SCRIPT=%~dp0refresh_all.bat"

echo Scheduling "%TASKNAME%" to run every day at 06:00
echo Script: %SCRIPT%
echo.

schtasks /create /tn "%TASKNAME%" /tr "\"%SCRIPT%\"" /sc daily /st 06:00 /f

if errorlevel 1 (
  echo.
  echo ---------------------------------------------------------------
  echo  FAILED to create the task.
  echo  Close this window, RIGHT-CLICK install_daily_task.bat and pick
  echo  "Run as administrator", then try again.
  echo ---------------------------------------------------------------
) else (
  echo.
  echo ---------------------------------------------------------------
  echo  Scheduled.
  echo    See it:     schtasks /query /tn "%TASKNAME%"
  echo    Run it now: schtasks /run   /tn "%TASKNAME%"
  echo    Remove it:  schtasks /delete /tn "%TASKNAME%" /f
  echo ---------------------------------------------------------------
)
echo.
pause
