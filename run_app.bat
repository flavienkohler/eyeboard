@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo EyeBoard needs "uv" ^(a fast Python package manager^), which is not installed.
  choice /m "Install it now"
  if errorlevel 2 exit /b 1
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

uv run eyeboard %*
if errorlevel 1 pause
