@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0\.."

set "PYTHON_EXE="

REM 1. Check local virtual environments
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist "venv\Scripts\python.exe" if not defined PYTHON_EXE set "PYTHON_EXE=venv\Scripts\python.exe"

REM 2. Check standard Windows per-user Python install paths
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"

REM 3. Check Program Files Python paths
if not defined PYTHON_EXE if exist "%ProgramFiles%\Python311\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"
if not defined PYTHON_EXE if exist "%ProgramFiles%\Python312\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python312\python.exe"
if not defined PYTHON_EXE if exist "%ProgramFiles%\Python310\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python310\python.exe"

REM 4. Check Python launcher (py)
if not defined PYTHON_EXE (
    py -3 -c "import sys" >nul 2>nul
    if !ERRORLEVEL! equ 0 set "PYTHON_EXE=py -3"
)

REM 5. Check PATH python
if not defined PYTHON_EXE (
    python -c "import sys" >nul 2>nul
    if !ERRORLEVEL! equ 0 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
    echo [ERROR] Python was not found in standard user directories or PATH.
    echo Please install Python 3.10+ from https://www.python.org.
    pause
    exit /b 1
)

echo Using Python: !PYTHON_EXE!
"!PYTHON_EXE!" .dev\scripts\build_installer.py %*

