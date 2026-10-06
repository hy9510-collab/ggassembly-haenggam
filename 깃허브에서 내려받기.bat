@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 인터넷(깃허브)에 올라온 최신 자료를 내 PC로 받아옵니다...
echo.
git add -A
git diff --cached --quiet
if %errorlevel%==0 goto pull
git commit -m "chore: 내려받기 전 로컬 변경 저장"
:pull
git pull --rebase
if errorlevel 1 (
  echo.
  echo 받아오지 못했습니다. 인터넷 연결을 확인해 주세요.
) else (
  echo.
  echo 최신 상태입니다.
)
if not "%1"=="auto" pause
