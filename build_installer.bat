@echo off
chcp 65001 >nul
REM Build Output\sPDF_Setup_X.X.X.exe with Inno Setup.
REM Prerequisite: run build_exe.bat first to create dist\sPDF.

if not exist dist\sPDF\sPDF.exe (
  echo dist\sPDF\sPDF.exe is missing. Run build_exe.bat first.
  exit /b 1
)
if not exist dist\sPDF-ocr\spdf-ocr.exe (
  echo dist\sPDF-ocr\spdf-ocr.exe is missing. Run build_exe.bat first.
  exit /b 1
)

set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
  echo Inno Setup 6 was not found: %ISCC%
  echo Install it from https://jrsoftware.org/isdl.php
  exit /b 1
)

%ISCC% installer.iss || goto :err
echo.
echo Complete: Output\sPDF_Setup_*.exe
goto :eof

:err
echo *** Installer build failed ***
exit /b 1
