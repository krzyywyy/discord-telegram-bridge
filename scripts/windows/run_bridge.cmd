@echo off
setlocal

REM Resolve repo root (two levels up from scripts\windows)
set "ROOT=%~dp0..\.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
cd /d "%ROOT%"

if not exist "data" mkdir "data"

set "PY="
if exist ".venv\\Scripts\\python.exe" set "PY=.venv\\Scripts\\python.exe"
if "%PY%"=="" (
  for %%P in (python.exe) do set "PY=%%~$PATH:P"
)

if "%PY%"=="" (
  echo [%DATE% %TIME%] Python not found on PATH and .venv is missing.>>"data\\bridge.log"
  exit /b 1
)

echo [%DATE% %TIME%] Starting bridge from %CD%>>"data\\bridge.log"
"%PY%" main.py >>"data\\bridge.log" 2>&1

endlocal

