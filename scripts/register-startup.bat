@echo off
title JARVIS - Windows Auto-Start Registration
setlocal enabledelayedexpansion

echo ============================================
echo   JARVIS AI Assistant - Auto-Start Setup
echo ============================================
echo.

REM Find the project root (where this script is located)
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

REM Check for VBS launcher
set "VBS_PATH=%PROJECT_ROOT%\scripts\start-jarvis.vbs"

if not exist "%VBS_PATH%" (
    echo [ERROR] Startup script not found: %VBS_PATH%
    echo.
    echo Please make sure start-jarvis.vbs exists in the scripts folder.
    pause
    exit /b 1
)

REM Register in Windows Registry (HKCU Run)
echo [1/3] Registering JARVIS for Windows auto-start...

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" ^
    /v "JARVIS AI Assistant" ^
    /t REG_SZ ^
    /d "wscript.exe \"%VBS_PATH%\" //NoLogo" ^
    /f

if %ERRORLEVEL% equ 0 (
    echo   [OK] Registered successfully.
) else (
    echo   [WARNING] Registration may have failed. Try running as Administrator.
)

REM Verify registration
echo [2/3] Verifying registration...
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "JARVIS AI Assistant" >nul 2>&1

if %ERRORLEVEL% equ 0 (
    echo   [OK] Verified: JARVIS will start automatically with Windows.
) else (
    echo   [FAIL] Registration verification failed.
)

REM Create startup shortcut in Start Menu
echo [3/3] Creating Start Menu shortcut...
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTMENU%\JARVIS AI Assistant.lnk"

REM Use PowerShell to create the shortcut
powershell -NoProfile -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$sc = $ws.CreateShortcut('%SHORTCUT%'); " ^
    "$sc.TargetPath = 'wscript.exe'; " ^
    "$sc.Arguments = '\"%VBS_PATH%\" //NoLogo'; " ^
    "$sc.WorkingDirectory = '%PROJECT_ROOT%'; " ^
    "$sc.Description = 'JARVIS AI Assistant - Desktop AI'; " ^
    "$sc.Save();"

if exist "%SHORTCUT%" (
    echo   [OK] Shortcut created in Startup folder.
) else (
    echo   [WARNING] Could not create startup shortcut.
)

echo.
echo ============================================
echo   Setup Complete!
echo.
echo   JARVIS will now start automatically
echo   when you log into Windows.
echo.
echo   To remove auto-start, run:
echo     unregister-startup.bat
echo ============================================
echo.

pause
