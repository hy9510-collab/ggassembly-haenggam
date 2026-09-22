@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 행정사무감사 언론보도를 수집합니다...
"C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe" "뉴스수집.py"
echo.
echo 끝났습니다. index.html 을 새로고침하면 반영됩니다.
pause
