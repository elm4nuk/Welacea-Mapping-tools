<#
.SYNOPSIS
  Jalankan WALLACEA API dalam mode SIMULASI development (SIMULASI - BUKAN AI).

.DESCRIPTION
  Mengatur WALLACEA_DETECTOR=simulation HANYA untuk proses API ini. Tombol analisis akan membuat kotak kandidat
  buatan yang deterministik (foto sama -> kotak sama), berstatus pending, berlabel "SIMULASI - BUKAN AI".
  Gunanya hanya menguji alur aplikasi tanpa bobot model. Jangan dipakai untuk keputusan lapangan.

.EXAMPLE
  cd apps\api
  powershell -ExecutionPolicy Bypass -File .\scripts\run-simulation.ps1
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$ApiRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $ApiRoot ".venv\Scripts\python.exe" }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    Write-Host "[GAGAL] Python venv API tidak ditemukan: $Python" -ForegroundColor Red
    Write-Host "Buat sekali dari folder apps\api: py -3.12 -m venv .venv; .venv\Scripts\python -m pip install -r requirements.lock.txt"
    exit 2
}

$saved = @{}
foreach ($name in @("WALLACEA_DETECTOR", "PYTHONUTF8")) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, "Process") }
Push-Location $ApiRoot
try {
    $env:WALLACEA_DETECTOR = "simulation"
    $env:PYTHONUTF8 = "1"
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host " SIMULASI - BUKAN AI. Kandidat analisis adalah kotak buatan." -ForegroundColor Yellow
    Write-Host " Hanya untuk menguji alur aplikasi. Jangan untuk keputusan lapangan." -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host "Status: http://127.0.0.1:$Port/api/v1/health  |  Berhenti: Ctrl+C"
    & $Python -m app --port $Port
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name], "Process") }
}
exit $code
