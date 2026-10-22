@echo off
chcp 65001 >nul
cd /d "%~dp0"
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set D=%%d
echo [%D%] 행감 자료를 깃허브에 올립니다...
echo.

rem 혹시 지난번 작업이 중간에 멈춰 있으면 먼저 정리한다
if exist ".git\rebase-merge" (
  echo 지난번 정리되지 않은 작업이 있어 되돌립니다.
  git rebase --abort
)
if exist ".git\rebase-apply" git rebase --abort

git add -A
git diff --cached --quiet
if %errorlevel%==0 (
  echo 바뀐 내용이 없습니다. 인터넷에 올라온 최신 내용만 받아옵니다.
  git pull --rebase
  goto end
)
git commit -m "chore: 행감 자료 자동 갱신 %D%"
if errorlevel 1 goto fail

git fetch origin
git rebase origin/main
if errorlevel 1 goto fixnews
goto push

:fixnews
rem 기사 파일은 깃허브(클라우드 수집분)를 정답으로 삼는다
echo 기사 파일이 겹쳐 인터넷 쪽 기사로 맞춥니다...
git checkout --ours -- data/news.json data/news_data.js
git add data/news.json data/news_data.js
git diff --name-only --diff-filter=U > "%TEMP%\haenggam_conflict.txt"
for /f %%x in ("%TEMP%\haenggam_conflict.txt") do if %%~zx NEQ 0 goto giveup
git -c core.editor=true rebase --continue
if errorlevel 1 goto giveup

:push
git push
if errorlevel 1 goto fail
echo.
echo 완료했습니다. https://github.com/hy9510-collab/ggassembly-haenggam
goto end

:giveup
echo.
echo 기사 파일 말고 다른 곳에서 겹쳐 자동으로 풀지 못했습니다. 작업을 되돌립니다.
git rebase --abort
echo 클로드에게 "깃허브 올리기 충돌"이라고 알려 주세요.
goto end

:fail
echo.
echo 올리지 못했습니다. 인터넷 연결과 깃허브 로그인을 확인해 주세요.

:end
if not "%1"=="auto" pause
