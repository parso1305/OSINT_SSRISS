@echo off
rem Windows Task Scheduler entry point: run every due source once, append output to logs\scheduler.log, exit.
rem Set WEB_MONITOR_PYTHON to a full python.exe path if "python" is not on the task account's PATH.
rem Extra arguments are passed through (e.g. --source <id>).
cd /d "%~dp0.."
if not exist logs mkdir logs
if "%WEB_MONITOR_PYTHON%"=="" set WEB_MONITOR_PYTHON=python
"%WEB_MONITOR_PYTHON%" -m src.scheduler --once %* >> logs\scheduler.log 2>&1
exit /b %ERRORLEVEL%
