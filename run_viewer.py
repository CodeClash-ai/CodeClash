#!/usr/bin/env python3
"""
Launch script for the CodeClash Trajectory Viewer
"""

import argparse
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodeClash Trajectory Viewer")
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        default=None,
        help="Logs directory to search for game trajectories (defaults to ./logs)",
    )

    args = parser.parse_args()

    from codeclash.viewer import app
    from codeclash.viewer.app import set_log_base_directory

    # Set the logs directory if provided
    if args.directory:
        set_log_base_directory(args.directory)
        print(f"📁 Using logs directory: {Path(args.directory).resolve()}")
    else:
        print(f"📁 Using logs directory: {Path.cwd() / 'logs'}")

    print("🎮 Starting CodeClash Trajectory Viewer...")
    print("📊 Navigate to http://localhost:5001 to view game trajectories")
    print("🔧 Press Ctrl+C to stop the server")

    app.run(debug=True, host="0.0.0.0", port=5001)
