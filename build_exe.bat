@echo off
chcp 65001 >nul
REM Build dist\sPDF\sPDF.exe with PyInstaller.
REM Prerequisite: install PyInstaller and all application dependencies.

echo === Creating icons ===
python make_icons.py || goto :err

echo === Cleaning previous build ===
if exist build rmdir /s /q build
if exist dist\sPDF rmdir /s /q dist\sPDF

echo === PyInstaller ===
REM Use python -m so the Scripts directory does not need to be on PATH.
python -m PyInstaller --noconfirm --clean spdf.spec || goto :err

echo.
echo Complete: dist\sPDF\sPDF.exe
echo Next: run build_installer.bat to create the installer.
goto :eof

:err
echo.
echo *** Build failed ***
exit /b 1
