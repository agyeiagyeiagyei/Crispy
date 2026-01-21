#!/bin/bash
# Start React frontend dev server
# This script ensures the server starts properly and binds to port 3000

cd "$(dirname "$0")/../preview-app"

echo "Starting React development server..."
echo "This will take 15-30 seconds to compile..."
echo ""

PORT=3000 BROWSER=none npm start
