<#
.SYNOPSIS
  Periksa berkas bobot YOLO (.pt) sebelum dipakai WALLACEA API.

.DESCRIPTION
  Memastikan berkas ada, berekstensi .pt, paket ultralytics terpasang di .venv API, bobot dapat dibuka,
  model bertipe deteksi, menampilkan model.names, dan memvalidasi label map.
  Skrip ini TIDAK mengunduh bobot dan TIDAK memasang paket apa pun.

  Catatan: path .pt adalah NILAI parameter -ModelPath. Jangan mengetik path .pt sendirian di terminal;
  PowerShell akan menganggapnya perintah dan memberi error "is not recognized".

.EXAMPLE
  cd apps\api
  powershell -ExecutionPolicy Bypass -File .\scripts\check-model.ps1 -ModelPath "C:\Model Tanaman\best.pt" -LabelMap 'jagung=plant'

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\check-model.ps1 -ModelPath .\models\best.pt -LabelMap 'jagung=plant' -Image "C:\Foto Drone\DJI_0001.JPG"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path berkas .pt, mis. C:\Model\best.pt")]
    [string]$ModelPath,
    [Alias("LabelMap")]
    [string]$LabelMapJson = "",
    [string]$Image = "",
    [double]$Confidence = 0.35,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$ApiRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $ApiRoot ".venv\Scripts\python.exe" }

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    Write-Host "[GAGAL] Python venv API tidak ditemukan: $Python" -ForegroundColor Red
    Write-Host "Buat sekali dari folder apps\api:"
    Write-Host "  py -3.12 -m venv .venv"
    Write-Host "  .venv\Scripts\python -m pip install -r requirements.lock.txt"
    exit 2
}

# Label map lewat environment (bukan argumen): PowerShell 5.1 membuang tanda kutip ganda saat memanggil program
# native, sehingga JSON di argumen akan rusak. Variabel dipulihkan setelah pemeriksaan.
$saved = @{}
foreach ($name in @("WALLACEA_LABEL_MAP_JSON", "PYTHONUTF8")) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, "Process") }
try {
    $env:WALLACEA_LABEL_MAP_JSON = $LabelMapJson
    $env:PYTHONUTF8 = "1"
    $conf = $Confidence.ToString([Globalization.CultureInfo]::InvariantCulture)
    $pyArgs = @((Join-Path $PSScriptRoot "check_model.py"), "--model-path", $ModelPath, "--confidence", $conf)
    if ($Image) { $pyArgs += @("--image", $Image) }
    & $Python @pyArgs
    $code = $LASTEXITCODE
}
finally {
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name], "Process") }
}
if ($code -ne 0) {
    Write-Host ""
    Write-Host "Model BELUM siap (exit $code). Perbaiki pesan [GAGAL] di atas. API tetap bisa dipakai dalam mode manual." -ForegroundColor Yellow
}
exit $code
