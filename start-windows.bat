@echo off
setlocal
cd /d "%~dp0"
if defined DAGONGREN_PYTHON (
  "%DAGONGREN_PYTHON%" scripts\desktop_launcher.py %*
) else (
  py -3 --version >nul 2>&1
  if not errorlevel 1 (
    py -3 scripts\desktop_launcher.py %*
  ) else (
    python scripts\desktop_launcher.py %*
  )
)
if errorlevel 1 (
  echo Requires Python 3.10+. Set DAGONGREN_PYTHON to its full executable path if needed.
  pause
)
endlocal
