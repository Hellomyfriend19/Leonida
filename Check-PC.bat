@echo off
title Leonida Legacy - PC Check
rem Double-click to see whether this PC is ready to build (tools, disk, optional game package, GPU).
setlocal
cd /d "%~dp0"
echo.
echo  ==========================================
echo    L E O N I D A   L E G A C Y  -  PC Check
echo  ==========================================
echo.
set "PY="
for %%V in (3.14 3.13 3.12 3) do (
  if not defined PY (
    py -%%V -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY (
  where python >nul 2>nul && (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul && set "PY=python"
  )
)
if not defined PY (
  echo Python 3.12 or newer is needed: https://www.python.org/downloads/
  pause
  exit /b 1
)
%PY% -I "%~dp0scripts\pc_readiness.py" %*
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo Done.) else (echo Something is still missing. See above.)
pause
exit /b %RC%