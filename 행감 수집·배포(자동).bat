@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set LOG=data\_자동배포기록.txt

echo.>> "%LOG%"
echo ===== 시작 %date% %time:~0,5% >> "%LOG%"

echo [1/2] 기사 수집 중...
"C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe" 뉴스수집.py >> "%LOG%" 2>&1
if errorlevel 1 (echo    수집 실패 >> "%LOG%") else (echo    수집 완료 >> "%LOG%")

echo [2/2] 깃허브에 올리는 중...
call "깃허브 올리기.bat" auto >> "%LOG%" 2>&1
if errorlevel 1 (echo    업로드 실패 >> "%LOG%") else (echo    업로드 완료 >> "%LOG%")

echo ===== 끝 %date% %time:~0,5% >> "%LOG%"
echo.
echo 끝났습니다. 기록 : data\_자동배포기록.txt
if not "%1"=="auto" pause
