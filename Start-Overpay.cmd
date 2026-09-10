@echo off
cd /d "%~dp0"
if not exist ".venv-advisor\Scripts\python.exe" (
  py -3 -m venv .venv-advisor
  if errorlevel 1 exit /b 1
)
".venv-advisor\Scripts\python.exe" -m pip install -r requirements-optimizer.txt
if errorlevel 1 exit /b 1
".venv-advisor\Scripts\python.exe" overpay_forecast.py --open
if errorlevel 1 pause
