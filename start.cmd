@echo off
rem Opens SapulMRF: starts Docker Desktop if needed, starts the database, API and website, then opens the browser.
rem Double-click it, or run "start.cmd sim" to also start the simulated data.
setlocal
cd /d "%~dp0"

docker info >nul 2>&1
if not errorlevel 1 goto docker_ready
echo Starting Docker Desktop...
start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set tries=0
:wait_docker
timeout /t 3 /nobreak >nul
docker info >nul 2>&1
if not errorlevel 1 goto docker_ready
set /a tries+=1
if %tries% lss 60 goto wait_docker
echo.
echo Docker Desktop didn't start within 3 minutes. Open it yourself, wait for "Engine running", then run this again.
pause
exit /b 1

:docker_ready
echo Starting SapulMRF (a few minutes the first time)...
docker compose up -d --wait
if errorlevel 1 goto failed
if /i "%~1"=="sim" docker compose --profile sim up -d sim

start "" http://127.0.0.1:5174
echo.
echo SapulMRF is running at http://127.0.0.1:5174
echo To close it, double-click stop.cmd
exit /b 0

:failed
echo.
echo Something didn't start. See what went wrong with:  docker compose logs api
pause
exit /b 1
