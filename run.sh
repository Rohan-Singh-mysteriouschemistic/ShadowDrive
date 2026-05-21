#!/bin/bash

echo "=================================================="
echo "   Starting ShadowDrive++ Project"
echo "=================================================="

echo ""
echo "[1/4] Starting Docker containers (PostgreSQL, MinIO & Redis)..."
cd "Server-Logic/server" || exit
docker-compose up -d

echo ""
echo "[2/4] Starting FastAPI Backend Server..."
# Run the FastAPI server in the background (or in a new terminal if supported)
if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
    start cmd //k "uvicorn app.main:app --reload"
elif command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "uvicorn app.main:app --reload; exec bash" &
elif command -v xterm &> /dev/null; then
    xterm -e "uvicorn app.main:app --reload" &
else
    # Fallback to running in the background and logging
    uvicorn app.main:app --reload > server.log 2>&1 &
    echo "Server started in background (see server.log)"
fi

echo ""
echo "[3/4] Starting RQ Background Worker..."
# Run the RQ worker in the background (or in a new terminal if supported)
if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
    start cmd //k "rq worker shadowdrive-jobs --with-scheduler"
elif command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "rq worker shadowdrive-jobs --with-scheduler; exec bash" &
elif command -v xterm &> /dev/null; then
    xterm -e "rq worker shadowdrive-jobs --with-scheduler" &
else
    # Fallback to running in the background and logging
    rq worker shadowdrive-jobs --with-scheduler > worker.log 2>&1 &
    echo "Worker started in background (see worker.log)"
fi

echo ""
echo "[4/4] Starting Client Watcher Agent..."
cd "../../Client-Logic" || exit
if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
    start cmd //k "python watcher.py"
elif command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "python watcher.py; exec bash" &
elif command -v xterm &> /dev/null; then
    xterm -e "python watcher.py" &
else
    # Fallback to running in the background and logging
    python watcher.py > client.log 2>&1 &
    echo "Client started in background (see client.log)"
fi

echo ""
echo "All services have been launched!"
cd "../" || exit
echo "=================================================="
