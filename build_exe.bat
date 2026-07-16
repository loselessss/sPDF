@echo off
REM sPDF 실행 파일 빌드 — PyInstaller로 dist\sPDF\sPDF.exe 생성
REM 사전: pip install pyinstaller  (그리고 앱 의존성 전부 설치)

echo === 아이콘 생성 ===
python make_icons.py || goto :err

echo === 이전 빌드 정리 ===
if exist build rmdir /s /q build
if exist dist\sPDF rmdir /s /q dist\sPDF

echo === PyInstaller ===
REM `python -m` 로 호출 — Scripts 폴더가 PATH에 없어도 동작한다
python -m PyInstaller --noconfirm --clean spdf.spec || goto :err

echo.
echo 완료: dist\sPDF\sPDF.exe
echo 다음: build_installer.bat 로 설치 파일 생성
goto :eof

:err
echo.
echo *** 빌드 실패 ***
exit /b 1
