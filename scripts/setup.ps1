$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Creating the Python environment failed.' }
    }
    & '.venv\Scripts\python.exe' -m pip install -r requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Installing locked Python dependencies failed.' }
    & '.venv\Scripts\python.exe' -m pip install --no-deps -e .
    if ($LASTEXITCODE -ne 0) { throw 'Installing ZeroWall failed.' }
    & '.venv\Scripts\python.exe' scripts/setup_tokenizers.py
    if ($LASTEXITCODE -ne 0) { throw 'Installing public Token Factory tokenizer data failed.' }
    npm ci --prefix apps/web
    if ($LASTEXITCODE -ne 0) { throw 'Installing locked frontend dependencies failed.' }
    npm run build --prefix apps/web
    if ($LASTEXITCODE -ne 0) { throw 'Building the UI failed.' }
    & '.venv\Scripts\python.exe' scripts/doctor.py
    Write-Output 'Ready. Run .venv\Scripts\zerowall.exe serve, then .venv\Scripts\zerowall.exe open in another terminal.'
} finally { Pop-Location }
