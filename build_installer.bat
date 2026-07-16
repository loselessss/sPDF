@echo off
REM sPDF 설치 파일 빌드 — Inno Setup으로 Output\sPDF_Setup_X.X.X.exe 생성
REM 사전: build_exe.bat 를 먼저 실행해 dist\sPDF 가 있어야 함

if not exist dist\sPDF\sPDF.exe (
  echo dist\sPDF\sPDF.exe 가 없습니다. 먼저 build_exe.bat 를 실행하세요.
  exit /b 1
)
if not exist dist\sPDF-ocr\spdf-ocr.exe (
  echo dist\sPDF-ocr\spdf-ocr.exe 가 없습니다. 먼저 build_exe.bat 를 실행하세요.
  exit /b 1
)

set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
  echo Inno Setup 6 을 찾을 수 없습니다: %ISCC%
  echo https://jrsoftware.org/isdl.php 에서 설치하세요.
  exit /b 1
)

%ISCC% installer.iss || goto :err
echo.
echo 완료: Output\sPDF_Setup_*.exe
goto :eof

:err
echo *** 설치 파일 빌드 실패 ***
exit /b 1
