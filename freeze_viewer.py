#!/usr/bin/env python3
"""
Static Site Generator for CodeClash Trajectory Viewer

This script uses Frozen-Flask to generate a static version of the viewer
that can be served without a Flask server.
"""

import argparse
import shutil
from pathlib import Path

from flask_frozen import Freezer

from codeclash.viewer import app, set_log_base_directory, set_static_mode
from codeclash.viewer.app import find_all_game_folders


def setup_freezer(output_dir: str = "build") -> Freezer:
    """Set up the Frozen-Flask freezer with proper configuration"""

    # Configure Flask app for static generation
    app.config["FREEZER_DESTINATION"] = output_dir
    app.config["FREEZER_RELATIVE_URLS"] = True
    app.config["FREEZER_IGNORE_MIMETYPE_WARNINGS"] = True
    # Ensure HTML files have .html extension
    app.config["FREEZER_DEFAULT_MIMETYPE"] = "text/html"

    # Enable static mode
    set_static_mode(True)

    # Create freezer
    freezer = Freezer(app)

    @freezer.register_generator
    def url_generator():
        """Generate URLs for all game sessions to be included in static build"""

        # Always include the picker page
        yield "game_picker", {}

        # Find all game folders and generate URLs for each
        from codeclash.viewer.app import LOG_BASE_DIR

        game_folders = find_all_game_folders(LOG_BASE_DIR)

        game_count = 0
        for game_folder in game_folders:
            if game_folder["is_game"]:
                game_count += 1
                folder_name = game_folder["name"]
                # Generate URL for each game session using path parameters
                yield "game_view", {"folder_path": folder_name}
                # Also generate the old query-parameter version for backward compatibility
                yield "index", {"folder": folder_name}

        print(f"Generated URLs for {game_count} games from {len(game_folders)} total folders")

        # Also generate the root index (which redirects to picker)
        yield "index", {}

    return freezer


def main():
    """Main function to generate static site"""
    parser = argparse.ArgumentParser(description="Generate static version of CodeClash Trajectory Viewer")
    parser.add_argument("--logs-dir", type=str, default="logs", help="Directory containing game logs (default: logs)")
    parser.add_argument(
        "--output-dir", type=str, default="build", help="Output directory for static files (default: build)"
    )
    parser.add_argument("--clean", action="store_true", help="Clean output directory before building")

    args = parser.parse_args()

    # Set up paths
    logs_dir = Path(args.logs_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not logs_dir.exists():
        print(f"Error: Logs directory '{logs_dir}' does not exist")
        return 1

    # Set the logs directory for the app
    set_log_base_directory(logs_dir)

    # Clean output directory if requested
    if args.clean and output_dir.exists():
        print(f"Cleaning output directory: {output_dir}")
        shutil.rmtree(output_dir)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating static site from logs in: {logs_dir}")
    print(f"Output directory: {output_dir}")

    # Set up freezer
    freezer = setup_freezer(str(output_dir))

    # Generate static site
    try:
        print("Freezing Flask application...")
        freezer.freeze()

        # Post-process: Add .html extensions to files that don't have them
        print("Post-processing: Adding .html extensions...")
        _add_html_extensions(output_dir)

        print(f"✅ Static site generated successfully in: {output_dir}")
        print(f"📁 Open {output_dir}/index.html in your browser to view the static site")
        print(f"💡 For best results, serve via HTTP server: cd {output_dir} && python -m http.server 8000")

        return 0
    except Exception as e:
        print(f"❌ Error generating static site: {e}")
        return 1


def _add_html_extensions(build_dir: Path):
    """Add .html extensions to files that don't have .html extensions but contain HTML"""
    build_path = Path(build_dir)

    # Find files that might be HTML
    for file_path in build_path.rglob("*"):
        if file_path.is_file() and not file_path.name.endswith(".html"):
            # Skip known non-HTML files
            if file_path.name in ["load-readme"] or file_path.name.startswith("line-counts"):
                continue

            # Skip if it's in static directory
            if "static" in file_path.parts:
                continue

            # Check if file contains HTML content
            try:
                content = file_path.read_text()
                if content.strip().startswith("<!DOCTYPE html") or "<html" in content[:200]:
                    # Rename to add .html extension
                    new_path = file_path.with_name(file_path.name + ".html")
                    file_path.rename(new_path)
                    print(f"  Renamed: {file_path.relative_to(build_path)} -> {new_path.relative_to(build_path)}")
            except (UnicodeDecodeError, OSError):
                # Skip binary files or files we can't read
                continue


if __name__ == "__main__":
    exit(main())
