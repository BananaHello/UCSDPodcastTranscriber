#!/bin/bash

# UCSD Podcast Transcriber - Quick Start Script
# This script activates the virtual environment and starts the web app

echo "============================================================"
echo "🎓 UCSD Podcast Transcriber - Starting Web App"
echo "============================================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "📁 Working directory: $SCRIPT_DIR"
echo ""

# Check if virtual environment exists
if [ -d "venv-webapp" ]; then
    echo "✅ Found virtual environment: venv-webapp"
    echo "🔄 Activating virtual environment..."
    source venv-webapp/bin/activate
elif [ -d "venv" ]; then
    echo "✅ Found virtual environment: venv"
    echo "🔄 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  No virtual environment found."
    echo "   Creating one now: venv-webapp"
    echo ""
    python3 -m venv venv-webapp
    source venv-webapp/bin/activate
    echo "📦 Installing dependencies..."
    pip install -r requirements-webapp.txt
    echo ""
fi

echo "🚀 Starting Flask server..."
echo ""

# Start the app
python3 app.py
