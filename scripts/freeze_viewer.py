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
    # Don't fail on 404s (API endpoints return 404 in static mode)
    app.config["FREEZER_IGNORE_404_NOT_FOUND"] = True

    # Enable static mode
    set_static_mode(True)

    # Create freezer with custom configuration
    freezer = Freezer(app)

    # Explicitly register ALL generators to disable automatic route discovery
    # This prevents Flask-Frozen from trying to freeze API endpoints

    @freezer.register_generator
    def index():
        """Only freeze the root index"""
        print("  Generating URL for index...")
        yield {}

    @freezer.register_generator
    def game_picker():
        """Freeze game picker"""
        print("  Generating URL for game_picker...")
        yield {}

    @freezer.register_generator
    def game_view():
        """Freeze all game views"""
        from codeclash.viewer.app import LOG_BASE_DIR

        game_folders = find_all_game_folders(LOG_BASE_DIR)
        print(f"  Generating URLs for {len(game_folders)} game view(s)...")
        for game_folder in game_folders:
            yield {"folder_path": game_folder["name"]}

    # Register empty generators for API endpoints we want to skip
    @freezer.register_generator
    def download_file():
        return []

    @freezer.register_generator
    def load_log():
        return []

    @freezer.register_generator
    def load_trajectory_details():
        return []

    @freezer.register_generator
    def load_trajectory_diffs():
        return []

    @freezer.register_generator
    def delete_experiment():
        return []

    @freezer.register_generator
    def analysis_line_counts():
        return []

    @freezer.register_generator
    def batch_monitor():
        return []

    @freezer.register_generator
    def batch_api_jobs():
        return []

    @freezer.register_generator
    def guess_config_names():
        return []

    @freezer.register_generator
    def static():
        """Let Flask-Frozen handle static files automatically"""
        return

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

    assert logs_dir.exists()

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
    print("Freezing Flask application...")

    # Try to freeze - it will likely fail on API endpoints, but we'll continue
    try:
        urls = freezer.freeze()
        print(f"Successfully froze {len(urls)} URL(s)")
    except Exception as e:
        print(f"Initial freeze had errors (expected): {type(e).__name__}")

    # Now manually generate the game view pages
    print("Generating game view pages...")
    from codeclash.viewer.app import LOG_BASE_DIR, game_view

    game_folders = find_all_game_folders(LOG_BASE_DIR)
    print(f"Found {len(game_folders)} game folder(s) to process")

    for i, game_folder in enumerate(game_folders, 1):
        folder_path = game_folder["name"]
        print(f"  [{i}/{len(game_folders)}] Generating page for: {folder_path}")

        # Create the output directory structure
        game_output_dir = output_dir / "game" / folder_path
        game_output_dir.mkdir(parents=True, exist_ok=True)

        # Generate the HTML for this game
        with app.test_request_context(f"/game/{folder_path}"):
            try:
                html = game_view(folder_path)
                output_file = game_output_dir / "index.html"
                output_file.write_text(html)
                print(f"    ✓ Generated: {output_file.relative_to(output_dir)}")
            except Exception as e:
                print(f"    ✗ Error generating page: {e}")

    # Post-process: Clean up any conflicting files from API endpoints
    print("Post-processing: Cleaning up API endpoint files...")
    _cleanup_api_files(output_dir)

    # Post-process: Add .html extensions to files that don't have them
    print("Post-processing: Adding .html extensions...")
    _add_html_extensions(output_dir)

    print(f"✅ Static site generated successfully in: {output_dir}")
    print(f"📁 Open {output_dir}/index.html in your browser to view the static site")
    print(f"💡 For best results, serve via HTTP server: cd {output_dir} && python -m http.server 8000")


def _cleanup_api_files(build_dir: Path):
    """Remove API endpoint files that were created during freezing"""
    build_path = Path(build_dir)

    # List of files/directories to remove (API endpoints that shouldn't be in static build)
    cleanup_patterns = [
        "download-file",
        "load-log",
        "load-trajectory-details",
        "load-trajectory-diffs",
        "delete-experiment",
        "batch",
        "analysis",
        "picker/api",
    ]

    for pattern in cleanup_patterns:
        target = build_path / pattern
        if target.exists():
            if target.is_file():
                target.unlink()
                print(f"  Removed file: {pattern}")
            elif target.is_dir():
                shutil.rmtree(target)
                print(f"  Removed directory: {pattern}")


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
