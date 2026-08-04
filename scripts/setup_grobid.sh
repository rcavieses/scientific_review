#!/bin/bash
# Setup script for GROBID service

set -e

echo "🔧 GROBID Setup"
echo "==============="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

echo "✓ Docker found"
echo ""

# Check if GROBID is already running
echo "Checking if GROBID is already running..."
if curl -s http://localhost:8070/api/isalive > /dev/null 2>&1; then
    echo "✓ GROBID is already running at http://localhost:8070"
    exit 0
fi

echo "GROBID is not running. Starting Docker container..."
echo ""

# Pull latest GROBID image
echo "📥 Pulling GROBID Docker image (this may take a minute)..."
docker pull lfoppiano/grobid:latest

echo ""
echo "🚀 Starting GROBID service..."
docker run -d \
    --name grobid \
    -p 8070:8070 \
    lfoppiano/grobid:latest

echo ""
echo "⏳ Waiting for GROBID to be ready..."

# Wait for service to be ready (max 30 seconds)
COUNTER=0
while [ $COUNTER -lt 30 ]; do
    if curl -s http://localhost:8070/api/isalive > /dev/null 2>&1; then
        echo "✓ GROBID is ready!"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ GROBID setup complete!"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Service running at: http://localhost:8070"
        echo ""
        echo "To stop GROBID later:"
        echo "  docker stop grobid"
        echo ""
        echo "To start it again:"
        echo "  docker start grobid"
        echo ""
        exit 0
    fi

    sleep 1
    COUNTER=$((COUNTER + 1))
    echo -n "."
done

echo ""
echo "⚠️  GROBID startup timed out. The container may still be initializing."
echo "   Wait a moment and try: curl http://localhost:8070/api/isalive"
echo ""
