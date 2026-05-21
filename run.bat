@echo off
echo ==================================================
echo    Starting ShadowDrive++ Project
echo ==================================================

echo.
echo [1/4] Starting Docker containers (PostgreSQL, MinIO ^& Redis)...
cd "Server-Logic\server"
docker-compose up -d

echo.
echo [2/4] Starting FastAPI Backend Server...
:: Using start to open a new command prompt window for the server
start "ShadowDrive Backend Server" cmd /k "python -m uvicorn app.main:app --reload"

echo.
echo Waiting 5 seconds for the backend server to initialize...
timeout /t 5 /nobreak

echo.
echo [3/4] Starting RQ Background Worker...
:: Using start to open a new command prompt window for the RQ worker
start "ShadowDrive RQ Worker" cmd /k "rq worker shadowdrive-jobs --with-scheduler"

echo.
echo [4/4] Starting Client Watcher Agent...
cd "..\..\Client-Logic"
:: Using start to open another command prompt window for the client watcher
start "ShadowDrive Client Watcher" cmd /k "python watcher.py"

echo.
echo All services have been launched in separate windows!
cd ".."
echo ==================================================
