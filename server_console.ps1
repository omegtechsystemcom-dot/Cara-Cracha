$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonLocal = Join-Path $Root ".venv-local\Scripts\python.exe"
$PythonLegacy = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $PythonLocal) { $PythonLocal } else { $PythonLegacy }

Set-Location -LiteralPath $Root
& $Python run_server.py
