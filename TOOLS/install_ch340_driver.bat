@echo off
setlocal

:: eBALIK - CH340 USB-Serial Driver Installer
:: Installs the WCH CH340/CH341 driver needed for the LAFVIN UNO R3 board.

:: --- Re-launch elevated if not already running as Administrator ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================
echo   eBALIK - CH340 Driver Installer
echo ============================================
echo.

:: --- Report whether a CH340 device is already recognized ---
powershell -NoProfile -Command ^
  "$dev = Get-PnpDevice | Where-Object { $_.FriendlyName -like '*CH340*' -or $_.FriendlyName -like '*CH341*' }; if ($dev) { Write-Host 'CH340 driver already installed: ' $dev.FriendlyName } else { Write-Host 'No CH340 device currently detected. Proceeding with install.' }"

echo.
set DRIVER_PATH=%~dp0drivers\CH341SER.EXE

if not exist "%DRIVER_PATH%" (
    echo ERROR: Driver installer not found at:
    echo   %DRIVER_PATH%
    echo Place CH341SER.EXE in tools\drivers\ next to this script.
    pause
    exit /b 1
)

echo Launching CH340 driver installer...
echo A window will open - click "INSTALL" to proceed.
start /wait "" "%DRIVER_PATH%"

echo.
echo Installer finished. Plug in the LAFVIN UNO R3 now and check
echo Device Manager for "USB-SERIAL CH340 (COMx)" under Ports.
pause
