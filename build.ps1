# TopGear Build Script with PyInstaller
# This script activates the virtual environment and builds the project

Write-Host "[INFO] Starting TopGear build process..." -ForegroundColor Green

# Check if virtual environment exists
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "[ERROR] Virtual environment not found. Please run setup_venv.ps1 first." -ForegroundColor Red
    exit 1
}

# Activate virtual environment
Write-Host "[INFO] Activating virtual environment..." -ForegroundColor Cyan
& ".\venv\Scripts\Activate.ps1"

# Check if PyInstaller is installed
try {
    $pyinstallerVersion = pyinstaller --version 2>$null
    Write-Host "[SUCCESS] Found PyInstaller: $pyinstallerVersion" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] PyInstaller not found. Installing from requirements.txt..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# Clean previous build
Write-Host "[INFO] Cleaning previous build files..." -ForegroundColor Yellow
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}

# Build with PyInstaller using the existing spec file
Write-Host "[INFO] Building TopGear executable..." -ForegroundColor Cyan
pyinstaller simc_top_gear.spec --clean

# Check if build was successful (one-file build)
if (Test-Path "dist\simc_top_gear.exe") {
    Write-Host "[SUCCESS] Build completed successfully!" -ForegroundColor Green
    Write-Host "[INFO] Executable location: dist\simc_top_gear.exe" -ForegroundColor White
    
    # Get file size for info
    $fileSize = [math]::Round((Get-Item "dist\simc_top_gear.exe").Length / 1MB, 1)
    Write-Host "[INFO] File size: $fileSize MB" -ForegroundColor Cyan
    
    Write-Host ""
    Write-Host "[SUCCESS] TopGear is ready to use!" -ForegroundColor Green
    Write-Host "[INFO] Single executable file - no additional files needed!" -ForegroundColor Yellow
    Write-Host "[INFO] Run with: .\dist\simc_top_gear.exe" -ForegroundColor Yellow
} else {
    Write-Host "[ERROR] Build failed. Check the output above for errors." -ForegroundColor Red
    exit 1
}