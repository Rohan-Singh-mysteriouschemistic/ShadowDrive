#!/bin/bash

echo "=================================================="
echo "   Starting ShadowDrive++ Project"
echo "=================================================="

echo ""
echo "[1/5] Starting Docker containers (PostgreSQL, MinIO & Redis)..."
cd "Server-Logic/server" || exit
docker-compose up -d

echo ""
echo "[2/5] Starting FastAPI Backend Server..."
# Run the FastAPI server in the background (or in a new terminal if supported)
if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
    start cmd //k "python -m uvicorn app.main:app --reload"
elif command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "python -m uvicorn app.main:app --reload; exec bash" &
elif command -v xterm &> /dev/null; then
    xterm -e "python -m uvicorn app.main:app --reload" &
else
    # Fallback to running in the background and logging
    python -m uvicorn app.main:app --reload > server.log 2>&1 &
    echo "Server started in background (see server.log)"
fi

echo ""
echo "Waiting 5 seconds for the backend server to initialize..."
sleep 5

echo ""
echo "[3/5] Starting RQ Background Worker..."
# Run the RQ worker in the background (or in a new terminal if supported)
if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
    start cmd //k "python -m rq worker shadowdrive-jobs --with-scheduler -w rq.worker.SimpleWorker"
elif command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "python -m rq worker shadowdrive-jobs --with-scheduler; exec bash" &
elif command -v xterm &> /dev/null; then
    xterm -e "python -m rq worker shadowdrive-jobs --with-scheduler" &
else
    # Fallback to running in the background and logging
    python -m rq worker shadowdrive-jobs --with-scheduler > worker.log 2>&1 &
    echo "Worker started in background (see worker.log)"
fi

echo ""
echo "[4/5] Starting Local Client API Agent..."
cd "../../Client-Logic" || exit
if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
    start cmd //k "python local_api.py"
elif command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "python local_api.py; exec bash" &
elif command -v xterm &> /dev/null; then
    xterm -e "python local_api.py" &
else
    # Fallback to running in the background and logging
    python local_api.py > client.log 2>&1 &
    echo "Client started in background (see client.log)"
fi

echo ""
echo "[5/5] Starting UI Landing Page..."
cd "../shadowdrive-ui" || exit
if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
    start cmd //k "npm run dev -- --open"
elif command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "npm run dev -- --open; exec bash" &
elif command -v xterm &> /dev/null; then
    xterm -e "npm run dev -- --open" &
else
    # Fallback to running in the background and logging
    npm run dev > ui.log 2>&1 &
    echo "UI started in background (see ui.log). Open http://localhost:5173 in your browser."
fi

echo ""
echo "All services have been launched!"
cd "../" || exit
echo "=================================================="
