@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE="
where python >nul 2>nul
if %ERRORLEVEL% equ 0 set "PYTHON_EXE=python"
if not defined PYTHON_EXE (
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 set "PYTHON_EXE=py -3"
)
if not defined PYTHON_EXE (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
)
if not defined PYTHON_EXE (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)

if not defined PYTHON_EXE (
    echo [ERROR] Python was not found in PATH or standard user directories.
    echo Please install Python 3.10+ from https://www.python.org.
    pause
    exit /b 1
)

"%PYTHON_EXE%" scripts\build_installer.py %*

