@echo off
REM Batch file wrapper to reliably execute the MultiSportPredict Python application.
REM This ensures the script is run with the Python interpreter, which is the
REM correct way to run Python applications on Windows.
REM
REM Usage:
REM   run.bat soccer "Liverpool" "Arsenal"
REM   run.bat mlb "NYY" "BOS" --markets nrfi

python "%~dp0\predict_match.py" %*