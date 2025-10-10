#!/bin/bash
# Build script for production deployment

set -e

echo "📦 Building React frontend..."
cd frontend
npm install
npm run build
cd ..

echo "✅ Build complete!"
echo "Frontend built to: frontend/dist/"
echo ""
echo "To run the production server:"
echo "  python ../run_viewer_react.py"
