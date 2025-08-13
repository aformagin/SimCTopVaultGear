# TopGear Virtual Environment Setup Script
# Sets up Python 3.11 + PyQt5 environment for the TopGear SimC application

Write-Host "[INFO] Setting up TopGear virtual environment..." -ForegroundColor Green

# Check Python version
try {
    $pythonVersion = python --version 2>$null
    Write-Host "[INFO] Found Python: $pythonVersion" -ForegroundColor Cyan
    
    if ($pythonVersion -notmatch "3\.(11|12|13)") {
        Write-Host "[WARNING] Python 3.11 or higher recommended for best compatibility." -ForegroundColor Yellow
        Write-Host "[INFO] Current version should work, but if you encounter issues, consider Python 3.11." -ForegroundColor Yellow
    }
} catch {
    Write-Host "[ERROR] Python not found. Please install Python 3.11+ and add it to PATH." -ForegroundColor Red
    Write-Host "[INFO] Download from: https://www.python.org/downloads/" -ForegroundColor White
    exit 1
}

# Remove old virtual environment if it exists
if (Test-Path "venv") {
    Write-Host "[INFO] Removing existing virtual environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "venv"
}

# Create new virtual environment
Write-Host "[INFO] Creating virtual environment..." -ForegroundColor Cyan
python -m venv venv

if (-not (Test-Path "venv")) {
    Write-Host "[ERROR] Failed to create virtual environment." -ForegroundColor Red
    exit 1
}

Write-Host "[SUCCESS] Virtual environment created successfully." -ForegroundColor Green

# Activate virtual environment
Write-Host "[INFO] Activating virtual environment..." -ForegroundColor Cyan
& ".\venv\Scripts\Activate.ps1"

# Upgrade pip
Write-Host "[INFO] Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install requirements
Write-Host "[INFO] Installing PyQt5, PyInstaller, and dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt

# Verify installation
Write-Host "[INFO] Verifying installation..." -ForegroundColor Cyan
try {
    python -c "from PyQt5 import QtCore, QtWidgets; print('PyQt5 version:', QtCore.PYQT_VERSION_STR)"
    $pyinstallerVersion = pip show pyinstaller | Select-String "Version:" | ForEach-Object { $_.ToString().Split(":")[1].Trim() }
    
    Write-Host ""
    Write-Host "[SUCCESS] Environment setup complete!" -ForegroundColor Green
    Write-Host "[INFO] PyQt5 imported successfully" -ForegroundColor White
    Write-Host "[INFO] PyInstaller version: $pyinstallerVersion" -ForegroundColor White
    
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Test the application: python simc_top_gear.py" -ForegroundColor White
    Write-Host "2. Build executable: .\build.ps1" -ForegroundColor White
    Write-Host ""
    Write-Host "To manually activate this environment later:" -ForegroundColor Yellow
    Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
    
} catch {
    Write-Host "[ERROR] Installation verification failed." -ForegroundColor Red
    Write-Host "[INFO] Try running: pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}