@echo off
rem Open a web-monitor SQLite database in the sqlite3 shell (needs the sqlite3 CLI on PATH).
rem Usage:   scripts\open_db.bat [db-path] [sql]          default db-path: data\events.db
rem Example: scripts\open_db.bat data\live_demo.db "SELECT status, new_count, existing_count FROM runs;"
set "DB=%~1"
if "%DB%"=="" set "DB=%~dp0..\data\events.db"
sqlite3 "%DB%" %2
