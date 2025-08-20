"""
CodeClash Trajectory Viewer

A Flask-based web application to visualize AI agent game trajectories
"""

from .app import app, set_log_base_directory

__all__ = ["app", "set_log_base_directory"]
