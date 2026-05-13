@echo off
:: Run as Administrator to register .gcode file association
:: Right-click > Run as administrator

echo ========================================
echo   Register .gcode File Association
echo   (Harus dijalankan sebagai Administrator)
echo ========================================
echo.

set SCRIPT_DIR=%~dp0
set PYTHON_PATH=python

:: Register file type
reg add "HKCU\Software\Classes\.gcode" /ve /d "GCodeFile" /f
reg add "HKCU\Software\Classes\GCodeFile" /ve /d "GCode File" /f
reg add "HKCU\Software\Classes\GCodeFile\shell\open\command" /ve /d "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%gcode_viewer.py\" \"%%1\"" /f
reg add "HKCU\Software\Classes\GCodeFile\shell\Preview Thumbnail\command" /ve /d "\"%PYTHON_PATH%\" \"%SCRIPT_DIR%gcode_viewer.py\" \"%%1\"" /f

echo.
echo File association registered!
echo Sekarang kamu bisa double-click file .gcode untuk membukanya.
echo.
pause
