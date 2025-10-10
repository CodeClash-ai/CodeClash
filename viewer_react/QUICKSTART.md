# Quick Start Guide

## First Time Setup

1. **Install Python dependencies** (from project root):
   ```bash
   pip install flask flask-cors
   ```

2. **Install Node dependencies**:
   ```bash
   cd viewer_react/frontend
   npm install
   ```

## Development Mode (Recommended)

Run both servers in separate terminals for hot-reload:

**Terminal 1 - Backend:**
```bash
# From project root
python run_viewer_react.py
```

**Terminal 2 - Frontend:**
```bash
cd viewer_react/frontend
npm run dev
```

Then open http://localhost:3000 in your browser.

## Production Mode

Build the frontend and run from a single server:

```bash
cd viewer_react
./build.sh
cd ..
python run_viewer_react.py
```

Then open http://localhost:5002 in your browser.

## Custom Logs Directory

```bash
python run_viewer_react.py -d /path/to/your/logs
```

## Custom Port

```bash
python run_viewer_react.py --port 8080
```

## Troubleshooting

### Port already in use
If port 5002 is already in use (maybe the old viewer is running), use a different port:
```bash
python run_viewer_react.py --port 5003
```

### Frontend won't build
Make sure you have Node.js 18+ installed:
```bash
node --version
```

### Backend API errors
Check that all required Python packages are installed:
```bash
pip install flask flask-cors
```

Also ensure the codeclash package is installed in development mode:
```bash
pip install -e .
```
