#!/usr/bin/env bash
# Build script for Render deployment
# Installs Python deps + builds React frontend

set -o errexit  # exit on error

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Installing Node.js dependencies ==="
cd frontend
npm install

echo "=== Building React frontend ==="
npm run build

echo "=== Build complete ==="
ls -la dist/
cd ..
