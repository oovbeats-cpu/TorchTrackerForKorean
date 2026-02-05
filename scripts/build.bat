@echo off
REM TorchTracker Build Script
REM Builds the application into a distributable package

setlocal enabledelayedexpansion

echo ================================================
echo TorchTracker Build Script
echo ================================================

REM Get version from version.py
for /f "tokens=3 delims='" %%a in ('findstr /C:"__version__" src\titrack\version.py') do set VERSION=%%a
echo Building version: %VERSION%

REM Check if pyinstaller is available
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo Building with PyInstaller...
echo.

REM Clean previous builds
if exist "dist\TorchTracker" (
    echo Cleaning previous build...
    rmdir /s /q "dist\TorchTracker"
)
if exist "build" (
    rmdir /s /q "build"
)

REM Run PyInstaller
pyinstaller ti_tracker.spec --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed!
    exit /b 1
)

echo.
echo Verifying build...

REM Remove any data folder that might exist from testing
if exist "dist\TorchTracker\data" (
    echo Removing test data folder...
    rmdir /s /q "dist\TorchTracker\data"
)

REM Verify key files exist (PyInstaller 6.x uses _internal folder for data)
if not exist "dist\TorchTracker\TorchTracker.exe" (
    echo ERROR: TorchTracker.exe not found!
    exit /b 1
)
echo   [OK] TorchTracker.exe

if not exist "dist\TorchTracker\_internal\tlidb_items_seed_en.json" (
    echo ERROR: Items seed file not found!
    exit /b 1
)
echo   [OK] tlidb_items_seed_en.json

if not exist "dist\TorchTracker\_internal\titrack\web\static\index.html" (
    echo ERROR: Static web files not found!
    exit /b 1
)
echo   [OK] Static web files

echo.
echo Creating ZIP archive...

REM Create ZIP archive
set ZIP_NAME=TorchTracker-%VERSION%-windows.zip
cd dist
if exist "%ZIP_NAME%" del "%ZIP_NAME%"

REM Use PowerShell to create ZIP
powershell -Command "Compress-Archive -Path 'TorchTracker' -DestinationPath '%ZIP_NAME%' -Force"

if errorlevel 1 (
    echo ERROR: Failed to create ZIP archive!
    cd ..
    exit /b 1
)

cd ..

echo.
echo ================================================
echo Build complete!
echo ================================================
echo.
echo Output: dist\TorchTracker\
echo Archive: dist\%ZIP_NAME%
echo.
echo To test the build:
echo   cd dist\TorchTracker
echo   TorchTracker.exe
echo.

exit /b 0
