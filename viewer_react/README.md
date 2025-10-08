# CodeClash React Viewer

A modern React-based trajectory viewer for CodeClash game sessions.

## Features

- **Clean React + TypeScript frontend** with Vite for fast development
- **RESTful Flask backend** with clear API endpoints
- **Game Picker** - Browse and search all available games
- **Game Viewer** - View game overview, rounds, and results
- **Trajectory Viewer** - Inspect agent messages, diffs, and submissions
- **Lazy Loading** - Trajectories and diffs load on demand for better performance

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend development)

### Installation

1. Install Python dependencies (from project root):
```bash
pip install flask flask-cors
```

2. Install frontend dependencies:
```bash
cd viewer_react/frontend
npm install
```

### Development

For development with hot reload:

1. Start the backend server (from project root):
```bash
python run_viewer_react.py
```

2. In a separate terminal, start the frontend dev server:
```bash
cd viewer_react/frontend
npm run dev
```

The frontend will be available at http://localhost:3000 with hot reload.
The backend API runs at http://localhost:5002.

### Production

Build the frontend and serve it from Flask:

```bash
cd viewer_react/frontend
npm run build
cd ../..
python run_viewer_react.py
```

The app will be available at http://localhost:5002.

## Usage

```bash
# Use default logs directory (./logs)
python run_viewer_react.py

# Use custom logs directory
python run_viewer_react.py -d /path/to/logs

# Use custom port
python run_viewer_react.py --port 8000
```

## Architecture

```
viewer_react/
├── backend.py           # Flask REST API
├── frontend/            # React + TypeScript app
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── types/       # TypeScript types
│   │   ├── utils/       # API client
│   │   ├── App.tsx      # Main app component
│   │   └── main.tsx     # Entry point
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## API Endpoints

- `GET /api/folders` - List all game folders
- `GET /api/game/<path>` - Get game metadata and rounds
- `GET /api/trajectory/<path>/<player>/<round>` - Get trajectory data
- `GET /api/analysis/line-counts/<path>` - Get line count analysis
- `GET /api/analysis/sim-wins/<path>` - Get simulation wins per round
- `POST /api/delete-folder` - Delete a game folder

## Comparison with Original Viewer

### Improvements

- **Modern Stack**: React + TypeScript instead of Jinja templates
- **Better Performance**: Lazy loading, component-based architecture
- **Cleaner Code**: Separation of concerns between backend and frontend
- **Type Safety**: Full TypeScript support
- **Better UX**: Smooth interactions, clear visual hierarchy

### Simplified Features

- Removed static site generation (focus on live viewer)
- Simplified keyboard shortcuts (can be added back if needed)
- Removed some advanced features like matrix analysis display (can be added back)
- No folder management features yet (rename, move, etc.)

## Development Notes

The viewer focuses on core functionality with a clean, maintainable codebase. Additional features from the original viewer can be added incrementally as needed.
