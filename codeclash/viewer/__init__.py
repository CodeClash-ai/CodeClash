"""
CodeClash Trajectory Viewer

A Flask-based web application to visualize AI agent game trajectories
"""

from .app import app, is_static_mode, set_log_base_directory, set_static_mode

__all__ = ["app", "set_log_base_directory", "set_static_mode", "is_static_mode"]
