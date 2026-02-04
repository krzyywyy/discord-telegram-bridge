@echo off
setlocal

REM Resolve repo root (two levels up from scripts\windows)
set "ROOT=%~dp0..\.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
cd /d "%ROOT%"

if not exist "data" mkdir "data"

set "VENV_PY=.venv\\Scripts\\python.exe"
set "SYS_PY="
for %%P in (python.exe) do set "SYS_PY=%%~$PATH:P"

set "PY="
if exist "%VENV_PY%" (
  set "PY=%VENV_PY%"
) else (
  set "PY=%SYS_PY%"
)

if "%PY%"=="" (
  echo [%DATE% %TIME%] Python not found on PATH and .venv is missing.>>"data\\bridge.log"
  exit /b 1
)

if not exist "%VENV_PY%" (
  echo [%DATE% %TIME%] Creating venv...>>"data\\bridge.log"
  "%SYS_PY%" -m venv .venv >>"data\\bridge.log" 2>&1
  if errorlevel 1 exit /b 1

  echo [%DATE% %TIME%] Installing dependencies...>>"data\\bridge.log"
  "%VENV_PY%" -m pip install -r requirements.txt >>"data\\bridge.log" 2>&1
  if errorlevel 1 exit /b 1
)

echo [%DATE% %TIME%] Starting bridge from %CD%>>"data\\bridge.log"
"%VENV_PY%" main.py >>"data\\bridge.log" 2>&1

endlocal
