@echo off
REM TopGear Build Script with PyInstaller
REM This script activates the virtual environment and builds the project

echo [INFO] Starting TopGear build process...

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Please run setup_venv.bat first.
    pause
    exit /b 1
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if PyInstaller is installed
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] PyInstaller not found. Installing from requirements.txt...
    pip install -r requirements.txt
) else (
    for /f "tokens=*" %%i in ('pyinstaller --version') do set PYINSTALLER_VERSION=%%i
    echo [SUCCESS] Found PyInstaller: %PYINSTALLER_VERSION%
)

REM Clean previous build
echo [INFO] Cleaning previous build files...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM Build with PyInstaller using the existing spec file
echo [INFO] Building TopGear executable...
pyinstaller simc_top_gear.spec --clean

REM Check if build was successful (one-file build)
if exist "dist\simc_top_gear.exe" (
    echo [SUCCESS] Build completed successfully!
    echo [INFO] Executable location: dist\simc_top_gear.exe
    echo [INFO] Single executable file - no additional files needed!
    echo [INFO] Run with: .\dist\simc_top_gear.exe
    echo.
    echo [SUCCESS] TopGear is ready to use!
) else (
    echo [ERROR] Build failed. Check the output above for errors.
    pause
    exit /b 1
)

pause