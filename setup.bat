@echo off
setlocal
cd /d "%~dp0"
if not exist .cache mkdir .cache
if not exist .cache\tmp mkdir .cache\tmp
set "TEMP=%CD%\.cache\tmp"
set "TMP=%CD%\.cache\tmp"
set "PIP_CACHE_DIR=%CD%\.cache\pip"
set "PYTHONNOUSERSITE=1"
if not defined DELTA_PYTHON_VERSION set "DELTA_PYTHON_VERSION=3"
py -%DELTA_PYTHON_VERSION% --version >nul 2>&1
if errorlevel 1 (
 echo Python 3.11 or newer is required. Install it from python.org, then run this file again.
 if /i not "%~1"=="--no-pause" pause
 exit /b 1
)
py -%DELTA_PYTHON_VERSION% -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11 or newer required'"
if errorlevel 1 goto failed
if not exist .venv\Scripts\python.exe py -%DELTA_PYTHON_VERSION% -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Double-click start_dashboard.bat.
if /i not "%~1"=="--no-pause" pause
exit /b 0
:failed
echo Setup failed. Read the error above; no global packages were installed.
if /i not "%~1"=="--no-pause" pause
exit /b 1
