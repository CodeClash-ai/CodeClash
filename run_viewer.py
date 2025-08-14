#!/usr/bin/env python3
"""
Launch script for the CodeClash Trajectory Viewer
"""

if __name__ == "__main__":
    from codeclash.viewer import app

    print("🎮 Starting CodeClash Trajectory Viewer...")
    print("📊 Navigate to http://localhost:5001 to view game trajectories")
    print("🔧 Press Ctrl+C to stop the server")

    app.run(debug=True, host="0.0.0.0", port=5001)
