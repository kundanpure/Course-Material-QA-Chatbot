#!/usr/bin/env bash
# Render start script for StudyAI Backend
# This script is called by Render to start the application

echo "Starting StudyAI Backend on port $PORT..."
uvicorn production_agentic:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --timeout-keep-alive 120
