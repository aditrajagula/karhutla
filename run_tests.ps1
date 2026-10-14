# ==============================================================================
# Script Eksekusi Pengujian Backend - Proyek Pantau Hotspot (FireGuard)
# Mendukung eksekusi seluruh suite backend (105 tests) atau filter per modul
# ==============================================================================

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("all", "core", "raster", "citizen", "fast")]
    [string]$Suite = "all",

    [switch]$VerboseOutput
)

$ErrorActionPreference = "Stop"

# Tentukan path Python virtual environment
$VenvPytest = Join-Path $PSScriptRoot ".venv\Scripts\pytest.exe"
if (-not (Test-Path $VenvPytest)) {
    Write-Host "[!] Virtual environment tidak ditemukan di .venv. Menggunakan pytest di PATH..." -ForegroundColor Yellow
    $PytestCmd = "pytest"
} else {
    $PytestCmd = $VenvPytest
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   EKSEKUSI SUITE PENGUJIAN BACKEND (FIREGUARD/KARHUTLA)   " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$TargetPaths = @()
switch ($Suite) {
    "all" {
        Write-Host ">> Menjalankan SELURUH suite backend (15 file pengujian, 113 tests)..." -ForegroundColor Green
        $TargetPaths = @("backend/tests")
    }
    "core" {
        Write-Host ">> Menjalankan modul inti FIRMS, Geospasial Nasional & Integrasi Frontend (50 tests)..." -ForegroundColor Green
        $TargetPaths = @(
            "backend/tests/test_validation.py",
            "backend/tests/test_cleaner.py",
            "backend/tests/test_spatial_filter.py",
            "backend/tests/test_snapshot_manager.py",
            "backend/tests/test_firms_integration.py",
            "backend/tests/test_pipeline.py",
            "backend/tests/test_api_endpoints.py",
            "backend/tests/test_hotspots.py",
            "backend/tests/test_audit_pipeline_independent.py",
            "backend/tests/test_frontend_integration_live.py"
        )
    }
    "raster" {
        Write-Host ">> Menjalankan modul Hansen GFC Raster & Analisis Kalimantan (43 tests)..." -ForegroundColor Green
        $TargetPaths = @(
            "backend/tests/test_kalimantan_spatial.py",
            "backend/tests/test_hansen_raster_integration.py",
            "backend/tests/test_forest_change.py"
        )
    }
    "citizen" {
        Write-Host ">> Menjalankan modul Laporan Bukti Warga & Proteksi Privasi (20 tests)..." -ForegroundColor Green
        $TargetPaths = @(
            "backend/tests/test_citizen_reports.py",
            "backend/tests/test_citizen_evidence_and_privacy.py"
        )
    }
    "fast" {
        Write-Host ">> Menjalankan pengujian cepat (mengecualikan uji integrasi live)..." -ForegroundColor Green
        $TargetPaths = @("backend/tests", "-k", "not test_frontend_backend_integration")
    }
}

$PytestArgs = @()
if ($VerboseOutput -or $Suite -ne "all") {
    $PytestArgs += "-v"
}
$PytestArgs += $TargetPaths

Write-Host "Perintah: $PytestCmd $($PytestArgs -join ' ')" -ForegroundColor Gray
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray

$StopWatch = [System.Diagnostics.Stopwatch]::StartNew()

& $PytestCmd @PytestArgs
$ExitCode = $LASTEXITCODE

$StopWatch.Stop()
$Duration = [math]::Round($StopWatch.Elapsed.TotalSeconds, 2)

Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
if ($ExitCode -eq 0) {
    Write-Host "[OK] SELURUH PENGUJIAN LULUS (Durasi: $Duration detik)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] TERDAPAT PENGUJIAN GAGAL DENGAN EXIT CODE: $ExitCode" -ForegroundColor Red
}
Write-Host "============================================================" -ForegroundColor Cyan

exit $ExitCode

