@echo off
setlocal
cd /d "%~dp0"
rem Pinned dependencies have prebuilt Windows x64 packages for Python 3.11/3.12.
rem Never fall back to compiling DuckDB or other dependencies on the user's PC.
if defined DELTA_PYTHON_VERSION goto check_python
py -3.12 -c "import struct,sys; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 (
 set "DELTA_PYTHON_VERSION=3.12"
 goto check_python
)
py -3.11 -c "import struct,sys; assert sys.version_info[:2] == (3,11) and struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 (
 set "DELTA_PYTHON_VERSION=3.11"
 goto check_python
)
echo Install Python 3.12 Windows installer 64-bit from python.org, including the Python launcher.
echo Other Python versions may stay installed. This project will use Python 3.12.
goto failed
:check_python
py -%DELTA_PYTHON_VERSION% -c "import struct,sys; assert sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize('P') == 8, 'Use 64-bit Python 3.11 or 3.12'"
if errorlevel 1 goto failed
py -%DELTA_PYTHON_VERSION% -c "from pathlib import Path; import sys; sys.exit(0 if len(str(Path.cwd())) <= 80 else 1)"
if errorlevel 1 (
 echo The project folder path is too long for reliable Windows package installation.
 echo Extract a fresh copy into a short folder such as C:\DeltaLab and run setup.bat there.
 goto failed
)
if not exist .cache mkdir .cache
if not exist .cache\tmp mkdir .cache\tmp
set "TEMP=%CD%\.cache\tmp"
set "TMP=%CD%\.cache\tmp"
set "PIP_CACHE_DIR=%CD%\.cache\pip"
set "PYTHONNOUSERSITE=1"
if not exist .venv\Scripts\python.exe py -%DELTA_PYTHON_VERSION% -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -c "import struct,sys; assert sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize('P') == 8, 'Existing .venv is incompatible. Extract a fresh copy into a short folder and rerun setup.bat'"
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip check
if errorlevel 1 goto failed
echo Setup complete. Double-click start_dashboard.bat.
if /i not "%~1"=="--no-pause" pause
exit /b 0
:failed
echo Setup failed. Read the error above; no global packages or Windows settings were changed.
echo Dependencies must have prebuilt packages; this installer will not compile them.
if /i not "%~1"=="--no-pause" pause
exit /b 1
