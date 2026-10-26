$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -m pip install -e . --no-deps
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }
if (-not (Test-Path -LiteralPath 'config\local.toml')) {
    Copy-Item -LiteralPath 'config\design.toml' -Destination 'config\local.toml'
}
Write-Host 'Ready. Edit config/local.toml, then follow docs/DEPLOYMENT.md.'
