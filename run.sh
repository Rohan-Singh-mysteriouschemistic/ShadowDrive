#!/bin/bash

echo "=================================================="
echo "   Starting ShadowDrive++ Project"
echo "=================================================="

# Parse command line options to support running server-only or client-only
START_SERVER=true
START_CLIENT=true

while [[ $# -gt 0 ]]; do
  case $1 in
    --server|-s)
      START_SERVER=true
      START_CLIENT=false
      shift
      ;;
    --client|-c)
      START_SERVER=false
      START_CLIENT=true
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  -s, --server    Start only server-side components (Docker, FastAPI Backend, RQ Worker)"
      echo "  -c, --client    Start only client-side components (Client API Agent, UI)"
      echo "  -h, --help      Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--server|-s] [--client|-c]"
      exit 1
      ;;
  esac
done

ROOT_DIR="$PWD"

if [ "$START_SERVER" = true ]; then
    echo ""
    echo "[1/5] Starting Docker containers (PostgreSQL, MinIO & Redis)..."
    cd "$ROOT_DIR/Server-Logic/server" || exit
    source .venv/bin/activate

    # Load environment variables from .env if it exists
    if [ -f .env ]; then
        set -a
        source .env
        set +a
    fi

    # Start docker services
    docker compose up -d

    # Ensure SECRET_KEY is set (required by app.utils since Sprint 1)
    export SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32)}"


    echo ""
    echo "[2/5] Starting FastAPI Backend Server..."
    # Run the FastAPI server in the background (or in a new terminal if supported)
    if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
        start cmd //k "python -m uvicorn app.main:app --reload --host 0.0.0.0"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        osascript -e "tell application \"Terminal\" to do script \"cd '$PWD' && set -a && [ -f .env ] && source .env && set +a && export SECRET_KEY='$SECRET_KEY' && source .venv/bin/activate && python -m uvicorn app.main:app --reload --host 0.0.0.0\""
    elif command -v gnome-terminal &> /dev/null; then
        gnome-terminal -- bash -c ".venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0; exec bash" &
    elif command -v xterm &> /dev/null; then
        xterm -e ".venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0" &
    else
        # Fallback to running in the background and logging
        .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 > server.log 2>&1 &
        echo "Server started in background (see server.log)"
    fi

    echo ""
    echo "Waiting 5 seconds for the backend server to initialize..."
    sleep 5


    echo ""
    echo "[3/5] Starting RQ Background Worker..."
    # Run the RQ worker in the background (or in a new terminal if supported)
    if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
        start cmd //k "rq worker shadowdrive-jobs --with-scheduler -w rq.worker.SimpleWorker"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        osascript -e "tell application \"Terminal\" to do script \"cd '$PWD' && set -a && [ -f .env ] && source .env && set +a && export SECRET_KEY='$SECRET_KEY' && source .venv/bin/activate && rq worker shadowdrive-jobs --with-scheduler -w rq.worker.SimpleWorker\""
    elif command -v gnome-terminal &> /dev/null; then
        gnome-terminal -- bash -c ".venv/bin/rq worker shadowdrive-jobs --with-scheduler; exec bash" &
    elif command -v xterm &> /dev/null; then
        xterm -e ".venv/bin/rq worker shadowdrive-jobs --with-scheduler" &
    else
        # Fallback to running in the background and logging
        .venv/bin/rq worker shadowdrive-jobs --with-scheduler > worker.log 2>&1 &
        echo "Worker started in background (see worker.log)"
    fi
fi

if [ "$START_CLIENT" = true ]; then
    echo ""
    echo "[4/5] Starting Local Client API Agent..."
    cd "$ROOT_DIR/Client-Logic" || exit
    if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
        start cmd //k "python local_api.py"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        osascript -e "tell application \"Terminal\" to do script \"cd '$PWD' && source ../Server-Logic/server/.venv/bin/activate && python local_api.py\""
    elif command -v gnome-terminal &> /dev/null; then
        gnome-terminal -- bash -c "../Server-Logic/server/.venv/bin/python local_api.py; exec bash" &
    elif command -v xterm &> /dev/null; then
        xterm -e "../Server-Logic/server/.venv/bin/python local_api.py" &
    else
        # Fallback to running in the background and logging
        ../Server-Logic/server/.venv/bin/python local_api.py > client.log 2>&1 &
        echo "Client started in background (see client.log)"
    fi

    echo ""
    echo "[5/5] Starting UI Landing Page..."
    cd "$ROOT_DIR/shadowdrive-ui" || exit
    if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
        start cmd //k "npm run dev -- --open"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        osascript -e "tell application \"Terminal\" to do script \"cd '$PWD' && npm run dev -- --open\""
    elif command -v gnome-terminal &> /dev/null; then
        gnome-terminal -- bash -c "npm run dev -- --open; exec bash" &
    elif command -v xterm &> /dev/null; then
        xterm -e "npm run dev -- --open" &
    else
        # Fallback to running in the background and logging
        npm run dev > ui.log 2>&1 &
        echo "UI started in background (see ui.log). Open http://localhost:5173 in your browser."
    fi
fi

echo ""
echo "All requested services have been launched!"
cd "$ROOT_DIR" || exit
echo "=================================================="
