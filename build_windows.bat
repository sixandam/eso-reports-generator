@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo  Lyn-Dan Heights ESO Reports - Windows Standalone Build Script
echo =====================================================================
echo.

cd /d "%~dp0"

:: 1. Check Python installation
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in PATH. Please install Python 3.10+ from python.org.
    pause
    exit /b 1
)

:: 2. Setup Virtual Environment
if not exist ".venv" (
    echo [1/6] Creating Python virtual environment...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [2/6] Activating virtual environment and installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt pyinstaller pillow
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install required packages.
    pause
    exit /b 1
)

:: 3. Generate Windows Icon (.ico)
echo [3/6] Generating multi-resolution application icon...
python scripts\make_icon.py
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to generate icon assets.
    pause
    exit /b 1
)

:: 4. Run PyInstaller Build
echo [4/6] Compiling standalone Windows executables with PyInstaller...
pyinstaller eso-reports.spec --clean --noconfirm
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller compilation failed.
    pause
    exit /b 1
)

:: 5. Create Portable ZIP distribution
echo [5/6] Creating portable ZIP archive...
if exist "dist\eso-reports-windows.zip" del /f /q "dist\eso-reports-windows.zip"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\eso-reports\*' -DestinationPath 'dist\eso-reports-windows.zip' -Force"

:: 6. Build Inno Setup Installer (if ISCC is found)
echo [6/6] Checking for Inno Setup compiler...
set "ISCC_PATH="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if defined ISCC_PATH (
    echo Compiling Windows setup installer with Inno Setup...
    "%ISCC_PATH%" assets\installer.iss
    if %ERRORLEVEL% equ 0 (
        echo [SUCCESS] Installer created: dist\eso-reports-setup.exe
    ) else (
        echo [WARNING] Inno Setup compilation encountered an issue.
    )
) else (
    echo [INFO] Inno Setup 6 was not detected. To build eso-reports-setup.exe, install Inno Setup from https://jrsoftware.org/isdl.php
)

echo.
echo =====================================================================
echo  Build Completed Successfully!
echo =====================================================================
echo  Generated Output Files in dist\:
if exist "dist\eso-reports-portable.exe" echo  - Portable Executable: dist\eso-reports-portable.exe
if exist "dist\eso-reports-windows.zip"  echo  - Portable ZIP Archive: dist\eso-reports-windows.zip
if exist "dist\eso-reports-setup.exe"    echo  - Setup Installer:     dist\eso-reports-setup.exe
echo =====================================================================
echo.
pause

