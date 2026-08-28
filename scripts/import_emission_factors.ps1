$ErrorActionPreference = "Stop"

$projectDirectory = "D:\Projects\CarbonIQ"
$pythonExecutable = Join-Path $projectDirectory ".venv\Scripts\python.exe"
$logDirectory = Join-Path $projectDirectory "logs"

Set-Location $projectDirectory

New-Item `
    -ItemType Directory `
    -Path $logDirectory `
    -Force | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"

$stdoutLog = Join-Path `
    $logDirectory `
    "emission-factor-import-$timestamp.out.log"

$stderrLog = Join-Path `
    $logDirectory `
    "emission-factor-import-$timestamp.err.log"

Write-Host "Starting CarbonIQ emission-factor import..."

$process = Start-Process `
    -FilePath $pythonExecutable `
    -ArgumentList @(
        "manage.py",
        "import_emission_factors"
    ) `
    -WorkingDirectory $projectDirectory `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -Wait `
    -PassThru

Write-Host ""
Write-Host "=== Import Output ==="

if (Test-Path $stdoutLog) {
    Get-Content $stdoutLog
}

if (Test-Path $stderrLog) {
    $stderrContent = Get-Content $stderrLog

    if ($stderrContent) {
        Write-Host ""
        Write-Host "=== Import Errors ==="
        $stderrContent
    }
}

Write-Host ""
Write-Host "Exit code: $($process.ExitCode)"

if ($process.ExitCode -ne 0) {
    Write-Host ""
    Write-Host "CarbonIQ emission-factor import FAILED."
    Write-Host "Output log : $stdoutLog"
    Write-Host "Error log  : $stderrLog"
    exit $process.ExitCode
}

Write-Host ""
Write-Host "CarbonIQ emission-factor import completed successfully."
