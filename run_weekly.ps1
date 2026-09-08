# Draait alle modules van CI Search Manager na elkaar en schrijft het weekrapport.
# Gebruik:  .\run_weekly.ps1            (of met -Email om het rapport te mailen)
# Taakplanner: zie README.md.
param([switch]$Email)

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { Write-Error "Geen .venv gevonden; zie README (Setup)"; exit 1 }

$log = Join-Path $PSScriptRoot "data\run_weekly.log"
"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm') ===" | Out-File -FilePath $log -Append -Encoding utf8

foreach ($module in @("src.ai_visibility", "src.seo_audit", "src.search_console")) {
    "--- $module" | Out-File -FilePath $log -Append -Encoding utf8
    & $python -m $module 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { "[fout] $module gaf exitcode $LASTEXITCODE" | Tee-Object -FilePath $log -Append }
}

$reportArgs = @("-m", "src.report")
if ($Email) { $reportArgs += "--email" }
& $python @reportArgs 2>&1 | Tee-Object -FilePath $log -Append
