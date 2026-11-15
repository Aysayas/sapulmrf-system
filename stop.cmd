@echo off
rem Closes SapulMRF: stops every container (the website, API, database, worker and simulator). Your data is kept.
cd /d "%~dp0"
docker compose --profile sim down
if errorlevel 1 (
  echo.
  echo Couldn't stop it. Is Docker Desktop running?
  pause
  exit /b 1
)
echo.
echo Stopped. Your data is kept; start.cmd opens it again.
