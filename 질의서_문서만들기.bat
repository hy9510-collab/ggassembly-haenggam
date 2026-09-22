@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 행감 질의서·자료요구 목록 문서를 만듭니다...
"D:\1. 김하영\AI 및 의회 관련 자료\바이브 코딩\실습\회의 발언카드 보도자료 비서\.venv\Scripts\python.exe" "질의서_문서만들기.py"
echo.
echo 문서 폴더를 엽니다.
start "" "%~dp0문서"
pause
