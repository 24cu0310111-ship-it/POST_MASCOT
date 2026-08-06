#!/bin/bash
# Start script for Multi-Agent Orchestrator (MAO)
# Usage:
#   ./start.sh              # Run backend + serve frontend from build/
#   ./start.sh --dev        # Run backend + frontend dev server (hot reload)
#   ./start.sh --backend    # Run backend only
#   ./start.sh --frontend   # Run frontend dev server only

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

MODE="${1:-full}"

start_backend() {
    echo "Starting FastAPI backend on http://localhost:8000 ..."
    echo "Swagger docs: http://localhost:8000/api/docs"
    . .venv/bin/activate
    python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
}

start_frontend_dev() {
    echo "Starting React dev server on http://localhost:3000 ..."
    cd frontend && npm start
}

start_frontend_serve() {
    if [ ! -d "frontend/build" ]; then
        echo "Building frontend for production..."
        cd frontend && npm run build && cd ..
    fi
    echo "Serving frontend from frontend/build/ ..."
    echo "  - Frontend: http://localhost:3000 (via npx serve)"
    cd frontend && npx serve -s build -l 3000
}

case "$MODE" in
    --dev)
        start_backend &
        BACKEND_PID=$!
        start_frontend_dev &
        FRONTEND_PID=$!
        echo ""
        echo "========================================="
        echo "  MAO is running!"
        echo "  Backend:  http://localhost:8000"
        echo "  Frontend: http://localhost:3000"
        echo "  Swagger:  http://localhost:8000/api/docs"
        echo "========================================="
        echo ""
        trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
        wait
        ;;
    --backend)
        start_backend
        ;;
    --frontend)
        start_frontend_serve
        ;;
    *)
        start_backend &
        BACKEND_PID=$!
        start_frontend_serve &
        FRONTEND_PID=$!
        echo ""
        echo "========================================="
        echo "  MAO is running!"
        echo "  Backend:  http://localhost:8000"
        echo "  Frontend: http://localhost:3000"
        echo "  Swagger:  http://localhost:8000/api/docs"
        echo "========================================="
        echo ""
        trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
        wait
        ;;
esac
