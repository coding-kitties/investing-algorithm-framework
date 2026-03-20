#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/docusaurus"

if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

if [ "$1" = "--build" ] || [ "$1" = "-b" ]; then
    echo "Building docs..."
    npm run build
    echo "Serving built docs..."
    npm run serve
else
    echo "Starting Docusaurus dev server..."
    npm start
fi
