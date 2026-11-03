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
set "PYTHONNOUSERSITE=1"
set "STREAMLIT_BROWSER_GATHER_USAGE_STATS=false"
if not defined DELTA_DASHBOARD_PORT set "DELTA_DASHBOARD_PORT=8501"
echo Open http://127.0.0.1:%DELTA_DASHBOARD_PORT% in your browser yourself. Press Ctrl+C here to stop.
.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1 --server.port=%DELTA_DASHBOARD_PORT% --server.headless=true --browser.gatherUsageStats=false
set "DASHBOARD_RESULT=%ERRORLEVEL%"
if not "%DASHBOARD_RESULT%"=="0" if /i not "%~1"=="--no-pause" pause
exit /b %DASHBOARD_RESULT%
