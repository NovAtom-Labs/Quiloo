$ErrorActionPreference = "Stop"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
$Launcher = Join-Path $RepositoryRoot "scripts\run_desktop_dev.py"

if (-not (Test-Path -Path $Python -PathType Leaf)) {
    Write-Error "Agent Kronig development setup is missing. Run: py -3.13 scripts\bootstrap_dev.py"
    exit 1
}

& $Python $Launcher
exit $LASTEXITCODE
