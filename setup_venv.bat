@echo off
REM TopGear Virtual Environment Setup Script
REM Sets up Python 3.11 + PyQt5 environment for the TopGear SimC application

echo [INFO] Setting up TopGear virtual environment...

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+ and add it to PATH.
    echo [INFO] Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [INFO] Found Python: %PYTHON_VERSION%

echo %PYTHON_VERSION% | findstr /R "3\.\(11\|12\|13\)" >nul
if errorlevel 1 (
    echo [WARNING] Python 3.11 or higher recommended for best compatibility.
    echo [INFO] Current version should work, but if you encounter issues, consider Python 3.11.
)

REM Remove old virtual environment if it exists
if exist "venv" (
    echo [INFO] Removing existing virtual environment...
    rmdir /s /q "venv"
)

REM Create new virtual environment
echo [INFO] Creating virtual environment...
python -m venv venv

if not exist "venv" (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [SUCCESS] Virtual environment created successfully.

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo [INFO] Installing PyQt5, PyInstaller, and dependencies...
pip install -r requirements.txt

REM Verify installation
echo [INFO] Verifying installation...
python -c "from PyQt5 import QtCore, QtWidgets; print('PyQt5 version:', QtCore.PYQT_VERSION_STR)" 2>nul
if errorlevel 1 (
    echo [ERROR] Installation verification failed.
    echo [INFO] Try running: pip install -r requirements.txt
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('pip show pyinstaller ^| findstr "Version:"') do set PYINSTALLER_VERSION=%%i

echo.
echo [SUCCESS] Environment setup complete!
echo [INFO] PyQt5 imported successfully
echo [INFO] PyInstaller version: %PYINSTALLER_VERSION%

echo.
echo Next steps:
echo 1. Test the application: python simc_top_gear.py
echo 2. Build executable: .\build.bat

echo.
echo To manually activate this environment later:
echo   venv\Scripts\activate.bat

pause