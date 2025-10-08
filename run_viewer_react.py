#!/usr/bin/env python3
"""
Launch script for the React-based CodeClash Trajectory Viewer
"""

import argparse
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodeClash React Trajectory Viewer")
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        default=None,
        help="Logs directory to search for game trajectories (defaults to ./logs)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5002,
        help="Port to run the server on (default: 5002)",
    )

    args = parser.parse_args()

    from viewer_react.backend import app, set_log_base_directory

    # Set the logs directory if provided
    if args.directory:
        set_log_base_directory(args.directory)
        print(f"📁 Using logs directory: {Path(args.directory).resolve()}")
    else:
        print(f"📁 Using logs directory: {Path.cwd() / 'logs'}")

    print("🎮 Starting CodeClash React Trajectory Viewer...")
    print(f"📊 Navigate to http://localhost:{args.port} to view game trajectories")
    print("🔧 Press Ctrl+C to stop the server")

    app.run(debug=True, host="0.0.0.0", port=args.port)
