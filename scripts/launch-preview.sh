#!/bin/bash
# Launch script for Glyphs Preview Tool
# Starts both the backend server and React frontend

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Please run: python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if required Python packages are installed
if ! python3 -c "import flask, flask_cors, fontTools, glyphsLib" 2>/dev/null; then
    echo "Error: Required Python packages not found. Please install:"
    echo "  pip install flask flask-cors fonttools glyphsLib"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "Error: npm is not installed. Please install npm first."
    exit 1
fi

# Check if React app dependencies are installed
if [ ! -d "preview-app/node_modules" ]; then
    echo "Installing React app dependencies..."
    cd preview-app
    npm install
    cd ..
fi

# Create log directory if it doesn't exist
mkdir -p /tmp

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down servers..."
    if [ ! -z "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null || true
    fi
    if [ ! -z "$REACT_PID" ]; then
        kill $REACT_PID 2>/dev/null || true
    fi
    # Kill any remaining processes
    pkill -f "glyphs-preview-server.py" 2>/dev/null || true
    pkill -f "react-scripts start" 2>/dev/null || true
    echo "Servers stopped."
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start backend server
echo "Starting backend server on port 5001..."
python3 scripts/glyphs-preview-server.py > /tmp/preview-server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > /tmp/preview-server.pid

# Wait a moment for server to start
sleep 2

# Check if server started successfully
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "Error: Backend server failed to start. Check /tmp/preview-server.log"
    exit 1
fi

echo "Backend server started (PID: $SERVER_PID)"

# Start React frontend
echo "Starting React frontend on port 3000..."
cd preview-app
npm start > /tmp/preview-app.log 2>&1 &
REACT_PID=$!
cd ..
echo $REACT_PID > /tmp/preview-app.pid

# Wait a moment for React app to start
sleep 3

echo ""
echo "=========================================="
echo "Glyphs Preview Tool is running!"
echo "=========================================="
echo ""
echo "Backend server: http://localhost:5001"
echo "Frontend app:   http://localhost:3000"
echo ""
echo "Logs:"
echo "  Backend: /tmp/preview-server.log"
echo "  Frontend: /tmp/preview-app.log"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for processes
wait
