$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$advisorPython = Join-Path $PSScriptRoot '.venv-advisor\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $advisorPython)) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundledPython) {
        & $bundledPython -m venv --system-site-packages .venv-advisor
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv .venv-advisor
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv .venv-advisor
    } else {
        throw 'Python 3.11 oder neuer muss installiert sein.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Die Python-Umgebung konnte nicht erstellt werden.' }
}
& $advisorPython -c "import importlib.util, sys; sys.exit(any(importlib.util.find_spec(x) is None for x in ['pandas', 'requests', 'dotenv', 'sklearn', 'matplotlib', 'numpy', 'IPython']))"
if ($LASTEXITCODE -ne 0) {
    & $advisorPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Die benoetigten Pakete konnten nicht installiert werden.' }
}
& $advisorPython advisor_server.py
