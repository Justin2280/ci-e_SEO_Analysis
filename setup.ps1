# Eenmalige setup van CI Search Manager op Windows.
# Gebruik: .\setup.ps1   (lukt dit niet: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Virtuele omgeving aanmaken (.venv)..."
    py -3.11 -m venv .venv
}
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --quiet --upgrade pip
& $python -m pip install --quiet -r requirements-dev.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "'.env' aangemaakt vanuit .env.example - vul daar je keys in." -ForegroundColor Yellow
} else {
    Write-Host "'.env' bestaat al, niet overschreven."
}

Write-Host "`nTests draaien..."
& $python -m pytest -q

Write-Host "`nControle van .env:"
& $python -m src.common --check-env
Write-Host "`nKlaar. Open .env in een editor, vul de keys in en draai daarna .\run_weekly.ps1"
