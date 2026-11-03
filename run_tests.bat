@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Run setup.bat first.
 if /i not "%~1"=="--no-pause" pause
 exit /b 1
)
if not exist .cache\tmp mkdir .cache\tmp
set "TEMP=%CD%\.cache\tmp"
set "TMP=%CD%\.cache\tmp"
.venv\Scripts\python.exe -m pytest -q --basetemp=.cache\pytest-tmp
set "TEST_RESULT=%ERRORLEVEL%"
if /i not "%~1"=="--no-pause" pause
exit /b %TEST_RESULT%
