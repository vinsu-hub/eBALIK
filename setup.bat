@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   eBALIK - Full Environment Setup
echo ============================================
echo.

:: --- 1. Check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found on PATH. Install Python 3.11+ from python.org
    echo and re-run this script.
    pause
    exit /b 1
)

:: --- 2. Virtual environment + dependencies ---
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo Installing Python dependencies...
pip install -r backend\requirements.txt

:: --- 3. CH340 driver ---
echo.
echo Running CH340 driver installer...
call TOOLS\install_ch340_driver.bat 2>nul || echo [SKIP] CH340 driver installer not found, skipping.

:: --- 4. Check MySQL ---
mysql --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: MySQL not found on PATH. Install MySQL Server 8.x and
    echo re-run this script, or set it up manually before continuing.
    pause
)

:: --- 5. .env setup ---
if not exist backend\.env (
    echo Creating backend\.env from template...
    copy backend\.env.example backend\.env
    echo Edit backend\.env now if this machine's MySQL credentials differ
    echo from the defaults, then press any key to continue.
    pause
)

:: --- 6. Optional schema/seed load ---
echo.
choice /M "Load schema.sql and seed_data.sql into MySQL now"
if !errorlevel! equ 1 (
    mysql -u root < backend\schema.sql
    mysql -u root < backend\seed_data.sql
    echo Database initialized.
)

echo.
echo ============================================
echo   Setup complete.
echo   Run: python backend\run.py
echo ============================================
pause
