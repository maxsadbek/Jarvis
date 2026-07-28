@echo off
title JARVIS - Remove Auto-Start
echo ============================================
echo   JARVIS AI Assistant - Remove Auto-Start
echo ============================================
echo.

REM Remove from Windows Registry (HKCU Run)
echo [1/2] Removing from Windows Registry...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" ^
    /v "JARVIS AI Assistant" ^
    /f >nul 2>&1

echo   [OK] Registry entry removed.

REM Remove Startup folder shortcut
echo [2/2] Removing Start Menu shortcut...
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTMENU%\JARVIS AI Assistant.lnk"

if exist "%SHORTCUT%" (
    del "%SHORTCUT%" >nul 2>&1
    echo   [OK] Startup shortcut removed.
) else (
    echo   [OK] No startup shortcut found.
)

echo.
echo ============================================
echo   Auto-start removed successfully.
echo.
echo   JARVIS will no longer start automatically.
echo ============================================
echo.
pause
