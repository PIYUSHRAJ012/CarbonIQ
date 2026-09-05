$ErrorActionPreference = "Stop"

# Resolve CarbonIQ project root from this script's location.
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "========================================="
Write-Host "CarbonIQ External Data Synchronization"
Write-Host "========================================="
Write-Host ""

# Verify that the virtual environment exists.
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonPath)) {
    Write-Error "CarbonIQ virtual environment was not found at:"
    Write-Error $PythonPath
    exit 1
}

Write-Host "Project root : $ProjectRoot"
Write-Host "Python       : $PythonPath"
Write-Host ""
Write-Host "Starting synchronization..."
Write-Host ""

try {
    & $PythonPath manage.py sync_external_data

    if ($LASTEXITCODE -ne 0) {
        Write-Error "External-data synchronization failed."
        exit $LASTEXITCODE
    }

    Write-Host ""
    Write-Host "External-data synchronization completed successfully."
    exit 0
}
catch {
    Write-Error "Unexpected synchronization error: $($_.Exception.Message)"
    exit 1
}