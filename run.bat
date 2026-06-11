@echo off
echo ==================================================
echo    Starting ShadowDrive++ Project
echo ==================================================

echo.
echo [1/5] Starting Docker containers (PostgreSQL, MinIO ^& Redis)...
cd "Server-Logic\server"
docker-compose up -d

echo.
echo [2/5] Starting FastAPI Backend Server...
:: Using start to open a new command prompt window for the server
start "ShadowDrive Backend Server" cmd /k "python -m uvicorn app.main:app --reload"

echo.
echo Waiting 5 seconds for the backend server to initialize...
timeout /t 5 /nobreak

echo.
echo [3/5] Starting RQ Background Worker...
:: Using start to open a new command prompt window for the RQ worker
start "ShadowDrive RQ Worker" cmd /k "python -m rq worker shadowdrive-jobs --with-scheduler -w rq.worker.SimpleWorker"

echo.
echo [4/5] Starting Local Client API Agent...
cd "..\..\Client-Logic"
:: Using start to open another command prompt window for the local api
start "ShadowDrive Local Client" cmd /k "python local_api.py"

echo.
echo [5/5] Starting UI Landing Page...
cd "..\shadowdrive-ui"
:: Using start to open the UI in dev mode
start "ShadowDrive UI" cmd /k "npm run dev -- --open"

echo.
echo All services have been launched in separate windows!
cd ".."
echo ==================================================
