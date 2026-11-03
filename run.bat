@echo off
rem Double-click to run Offline Tools from the source code (for development).
rem First run: creates the Python environment OUTSIDE OneDrive and installs everything.
rem Later runs: reinstalls only when pyproject.toml changed, then starts the app.
setlocal
set "VENV=%LOCALAPPDATA%\offline-tools\.venv"

if not exist "%VENV%\Scripts\python.exe" (
    echo First run: creating the Python environment in %VENV% ...
    python -m venv "%VENV%" || goto :setup_failed
)

"%VENV%\Scripts\python.exe" "%~dp0scripts\dev_env.py" || goto :setup_failed
start "" "%VENV%\Scripts\pythonw.exe" -m offline_tools %*
exit /b 0

:setup_failed
echo.
echo Setup failed. Check that Python 3.12 or newer is installed and on PATH:
echo     https://www.python.org/downloads/
pause
exit /b 1
