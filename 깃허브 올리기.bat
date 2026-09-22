@echo off
chcp 65001 >nul
cd /d "%~dp0"
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set D=%%d
echo [%D%] 행감 자료를 깃허브(비공개 저장소)에 올립니다...
echo.
git add -A
git diff --cached --quiet
if %errorlevel%==0 (
  echo 바뀐 내용이 없어 올리지 않았습니다.
  goto end
)
git commit -m "chore: 행감 자료 자동 갱신 %D%"
if errorlevel 1 goto fail
git push
if errorlevel 1 goto fail
echo.
echo 완료했습니다. https://github.com/hy9510-collab/ggassembly-haenggam
goto end

:fail
echo.
echo 올리지 못했습니다. 인터넷 연결과 깃허브 로그인을 확인해 주세요.

:end
if not "%1"=="auto" pause
