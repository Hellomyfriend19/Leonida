@echo off
title Leonida Legacy - Install prerequisites
setlocal
cd /d "%~dp0"
echo.
echo  Leonida Legacy - installs missing build tools (Python, .NET, Vulkan SDK, VS C++, llvm-mc).
echo  Does not download the game.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_prerequisites.ps1" %*
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo All set.) else (echo Something is still missing - read the messages above.)
pause
exit /b %RC%