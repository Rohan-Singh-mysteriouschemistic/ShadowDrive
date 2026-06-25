#!/bin/bash

echo "=================================================="
echo "   Stopping ShadowDrive++ Project"
echo "=================================================="

ROOT_DIR="$PWD"

STOP_SERVER=true
STOP_CLIENT=true

while [[ $# -gt 0 ]]; do
  case $1 in
    --server|-s)
      STOP_SERVER=true
      STOP_CLIENT=false
      shift
      ;;
    --client|-c)
      STOP_SERVER=false
      STOP_CLIENT=true
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  -s, --server    Stop only server-side components (Docker, FastAPI Backend, RQ Worker)"
      echo "  -c, --client    Stop only client-side components (Client API Agent, UI)"
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

if [ "$STOP_CLIENT" = true ]; then
    echo ""
    echo "Stopping Local Client API Agent..."
    pkill -f "python local_api.py" || echo "No Client API Agent process found."

    echo ""
    echo "Stopping UI Landing Page..."
    pkill -f "npm run dev" || echo "No npm run dev process found."
    pkill -f "vite" || echo "No vite process found."
fi

if [ "$STOP_SERVER" = true ]; then
    echo ""
    echo "Stopping RQ Background Worker..."
    pkill -f "rq worker shadowdrive-jobs" || echo "No RQ worker process found."

    echo ""
    echo "Stopping FastAPI Backend Server..."
    pkill -f "uvicorn app.main:app" || echo "No FastAPI Server process found."

    echo ""
    echo "Stopping Docker containers (PostgreSQL, MinIO & Redis)..."
    if [ -d "$ROOT_DIR/Server-Logic/server" ]; then
        cd "$ROOT_DIR/Server-Logic/server" || exit
        docker compose down
        cd "$ROOT_DIR" || exit
    else
        echo "Directory $ROOT_DIR/Server-Logic/server not found, skipping docker compose down."
    fi
fi

echo ""
echo "Stop process complete!"
echo "=================================================="
