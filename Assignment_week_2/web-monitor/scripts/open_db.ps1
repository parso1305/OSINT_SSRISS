# Open a web-monitor SQLite database in the sqlite3 shell (needs the sqlite3 CLI on PATH).
# Usage:   scripts\open_db.ps1 [-DbPath <path>] [sql ...]     default DbPath: data\events.db
# Example: scripts\open_db.ps1 -DbPath data\live_demo.db "SELECT status, new_count, existing_count FROM runs;"
param(
    [string]$DbPath = (Join-Path $PSScriptRoot "..\data\events.db"),
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$SqlArgs
)
sqlite3 $DbPath @SqlArgs
