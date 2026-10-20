<#
.SYNOPSIS
  Jalankan WALLACEA API dengan model YOLO tanaman (.pt) hasil pelatihan.

.DESCRIPTION
  1. Memeriksa model lewat check-model.ps1 (lewati dengan -SkipCheck).
  2. Mengatur WALLACEA_DETECTOR / WALLACEA_MODEL_PATH / WALLACEA_LABEL_MAP_JSON / WALLACEA_CONFIDENCE
     HANYA untuk proses API ini; nilainya dipulihkan saat API berhenti (Ctrl+C).
  3. Menjalankan .venv\Scripts\python -m app dari folder apps\api.
  Tidak mengunduh bobot dan tidak memasang paket.

.EXAMPLE
  cd apps\api
  powershell -ExecutionPolicy Bypass -File .\scripts\run-with-model.ps1 -ModelPath "C:\Model Tanaman\best.pt" -LabelMap 'jagung=plant'

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\run-with-model.ps1 -ModelPath .\models\best.pt -LabelMap 'jagung=plant,gulma=check' -Confidence 0.25 -Port 8000
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path berkas .pt, mis. C:\Model\best.pt")]
    [string]$ModelPath,
    [Parameter(Mandatory = $true, HelpMessage = "nama_kelas_model=plant|check|gap, mis. jagung=plant (JSON juga diterima)")]
    [Alias("LabelMap")]
    [string]$LabelMapJson,
    [ValidateRange(0.0, 1.0)]
    [double]$Confidence = 0.35,
    [int]$Port = 8000,
    [string]$ModelId = "",
    [switch]$NoPreload,
    [switch]$SkipCheck,
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

# Path relatif diartikan terhadap folder saat ini (sebelum pindah ke apps\api).
$ModelPath = $ModelPath.Trim().Trim('"').Trim("'")
if (-not [IO.Path]::IsPathRooted($ModelPath)) { $ModelPath = Join-Path (Get-Location).Path $ModelPath }
$ModelPath = [IO.Path]::GetFullPath($ModelPath)

if (-not $SkipCheck) {
    & (Join-Path $PSScriptRoot "check-model.ps1") -ModelPath $ModelPath -LabelMapJson $LabelMapJson -Confidence $Confidence -Python $Python
    if ($LASTEXITCODE -ne 0) {
        Write-Host "API tidak dijalankan dengan model. Untuk mode manual: .venv\Scripts\python -m app" -ForegroundColor Yellow
        exit $LASTEXITCODE
    }
    Write-Host ""
}

$vars = [ordered]@{
    WALLACEA_DETECTOR       = "ultralytics"
    WALLACEA_MODEL_PATH     = $ModelPath
    WALLACEA_LABEL_MAP_JSON = $LabelMapJson
    WALLACEA_CONFIDENCE     = $Confidence.ToString([Globalization.CultureInfo]::InvariantCulture)
    WALLACEA_MODEL_PRELOAD  = $(if ($NoPreload) { "false" } else { "true" })
    WALLACEA_MODEL_ID       = $(if ($ModelId) { $ModelId } else { $null })
    PYTHONUTF8              = "1"
}
$saved = @{}
foreach ($name in $vars.Keys) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, "Process") }
Push-Location $ApiRoot
try {
    foreach ($name in $vars.Keys) { [Environment]::SetEnvironmentVariable($name, $vars[$name], "Process") }
    Write-Host "WALLACEA API + model: $ModelPath"
    Write-Host "Label map: $LabelMapJson  |  confidence: $($vars.WALLACEA_CONFIDENCE)"
    Write-Host "Buka http://127.0.0.1:$Port/api/v1/health untuk status model. Berhenti: Ctrl+C."
    & $Python -m app --port $Port
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name], "Process") }
}
exit $code
