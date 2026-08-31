@echo off
REM start_bot.bat - keep the Discord bot running
REM
REM Double-click this. Leave the window open. Closing it stops the bot.
REM The bot only works while this is running and your PC is awake, so check
REM Settings > System > Power > Screen and sleep before you rely on it.
REM
REM It restarts itself if it crashes or the network drops, because a bot that
REM quietly died three hours ago is worse than one that never started.

cd /d "%~dp0"

:loop
echo.
echo [start_bot] launching at %DATE% %TIME%
venv\Scripts\python.exe msp_bot.py
echo [start_bot] exited with code %ERRORLEVEL% -- restarting in 15 seconds
echo [start_bot] press Ctrl+C twice to stop for good
timeout /t 15 /nobreak >nul
goto loop
