# Lyn-Dan Heights ESO Reports - Windows Standalone PowerShell Build Script
# Usage: powershell -ExecutionPolicy Bypass -File .\build_windows.ps1

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host " Lyn-Dan Heights ESO Reports - Windows Standalone Build Script" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python was not found in PATH. Please install Python 3.10+ from python.org." -ForegroundColor Red
    exit 1
}

# 2. Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "[1/6] Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "[2/6] Activating virtual environment and installing dependencies..." -ForegroundColor Yellow
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\pip.exe" install -r requirements.txt pyinstaller pillow

# 3. Generate Icon
Write-Host "[3/6] Generating multi-resolution application icon..." -ForegroundColor Yellow
& ".\.venv\Scripts\python.exe" scripts\make_icon.py

# 4. PyInstaller Build
Write-Host "[4/6] Compiling standalone Windows executables with PyInstaller..." -ForegroundColor Yellow
& ".\.venv\Scripts\pyinstaller.exe" eso-reports.spec --clean --noconfirm

# 5. Create Portable ZIP
Write-Host "[5/6] Creating portable ZIP archive..." -ForegroundColor Yellow
$zipPath = "dist\eso-reports-windows.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "dist\eso-reports\*" -DestinationPath $zipPath -Force

# 6. Inno Setup Compiler
Write-Host "[6/6] Checking for Inno Setup compiler..." -ForegroundColor Yellow
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
)

$isccPath = $null
foreach ($c in $isccCandidates) {
    if (Test-Path $c) { $isccPath = $c; break }
}

if ($isccPath) {
    Write-Host "Compiling Windows setup installer with Inno Setup..." -ForegroundColor Green
    & $isccPath assets\installer.iss
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] Installer created: dist\eso-reports-setup.exe" -ForegroundColor Green
    }
} else {
    Write-Host "[INFO] Inno Setup 6 was not detected. Install from https://jrsoftware.org/isdl.php to build eso-reports-setup.exe" -ForegroundColor Gray
}

Write-Host "`n=====================================================================" -ForegroundColor Cyan
Write-Host " Build Completed Successfully!" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Cyan
if (Test-Path "dist\eso-reports-portable.exe") { Write-Host " - Portable Executable: dist\eso-reports-portable.exe" -ForegroundColor Green }
if (Test-Path "dist\eso-reports-windows.zip")  { Write-Host " - Portable ZIP Archive: dist\eso-reports-windows.zip" -ForegroundColor Green }
if (Test-Path "dist\eso-reports-setup.exe")    { Write-Host " - Setup Installer:     dist\eso-reports-setup.exe" -ForegroundColor Green }
Write-Host "=====================================================================`n" -ForegroundColor Cyan

