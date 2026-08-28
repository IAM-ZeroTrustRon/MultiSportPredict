@echo off
REM ===================================================================
REM  DOUBLE-CLICK THIS FILE to commit and push this session's work.
REM  It cleans up the stale git state first, then shows you exactly
REM  what it is about to commit before it commits it.
REM ===================================================================
cd /d "%~dp0" 2>nul

echo ===============================================================
echo  STEP 1  Clearing stale git state
echo ===============================================================
if exist ".git\index.lock" (
  del /f /q ".git\index.lock"
  echo   removed stale .git\index.lock
) else (
  echo   no stale index.lock
)
if exist ".git\worktrees\i-want-to-run-the-soccer-match-between" (
  rmdir /s /q ".git\worktrees\i-want-to-run-the-soccer-match-between"
  echo   removed dead worktree registration from Aug 14
)
git worktree prune
echo.

echo ===============================================================
echo  STEP 2  What has changed
echo ===============================================================
git status --short
echo.
pause

echo ===============================================================
echo  STEP 3  Staging this session's files
echo ===============================================================
git add ingest_all_sports.py grade_predictions.py diagnose_sources.py
git add refresh_all.bat refresh_all.sh install_daily_task.bat run_diagnostic.bat push_to_github.bat
git add DAILY_INGESTION.md RESULTS_TRACKING.md .gitignore
git add team_stats_provider.py predict_match.py universal_runner.py models/tennis_predictor.py
echo.
echo  Staged:
git diff --cached --name-status
echo.
pause

echo ===============================================================
echo  STEP 4  Commit
echo ===============================================================
git commit -F commit_message.txt
echo.

echo ===============================================================
echo  STEP 5  Push to origin/main
echo ===============================================================
git push origin main
if errorlevel 1 (
  echo.
  echo  PUSH FAILED. Common causes:
  echo    - not signed in to GitHub ^(a browser window may have opened^)
  echo    - the remote has commits you do not have: run  git pull --rebase origin main
) else (
  echo.
  echo  Pushed. View at:
  echo    https://github.com/IAM-ZeroTrustRon/MultiSportPredict
)
echo.
pause
