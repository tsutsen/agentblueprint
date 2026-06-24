#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install
fi

# Run Vite dev server
echo "Starting graph visualization..."
npm run dev
