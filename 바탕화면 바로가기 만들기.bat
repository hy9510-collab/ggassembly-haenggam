@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 바탕화면에 「2026 행정사무감사 준비」 바로가기를 만듭니다...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop');" ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d '2026 행정사무감사 준비.lnk'));" ^
  "$s.TargetPath='%~dp0index.html'; $s.WorkingDirectory='%~dp0';" ^
  "$s.Description='경기도의회 문화체육관광위원회 2026 행정사무감사 준비'; $s.Save()"
echo.
echo 완료됐습니다. 바탕화면의 「2026 행정사무감사 준비」를 더블클릭하세요.
pause
