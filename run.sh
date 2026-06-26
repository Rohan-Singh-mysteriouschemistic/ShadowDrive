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
    # Always run in the background and log to server.log to avoid IDE terminal launch issues
    set -a; [ -f .env ] && source .env; set +a
    export SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32)}"
    .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 > server.log 2>&1 &
    echo "Server started in background (see server.log)"

    echo ""
    echo "Waiting 5 seconds for the backend server to initialize..."
    sleep 5


    echo ""
    echo "[3/5] Starting RQ Background Worker..."
    # Always run in the background and log to worker.log
    set -a; [ -f .env ] && source .env; set +a
    export SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32)}"
    .venv/bin/rq worker shadowdrive-jobs --with-scheduler -w rq.worker.SimpleWorker > worker.log 2>&1 &
    echo "Worker started in background (see worker.log)"
fi

if [ "$START_CLIENT" = true ]; then
    echo ""
    echo "[4/5] Starting Local Client API Agent..."
    cd "$ROOT_DIR/Client-Logic" || exit
    # Always run in the background and log to client.log
    ../Server-Logic/server/.venv/bin/python local_api.py > client.log 2>&1 &
    echo "Client started in background (see client.log)"

    echo ""
    echo "[5/5] Starting UI Landing Page..."
    cd "$ROOT_DIR/shadowdrive-ui" || exit
    # Always run in the background and log to ui.log
    npm run dev > ui.log 2>&1 &
    echo "UI started in background (see ui.log). Open http://localhost:5173 in your browser."
fi

echo ""
echo "All requested services have been launched!"
cd "$ROOT_DIR" || exit
echo "=================================================="
