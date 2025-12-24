from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console
from rich.text import Text

_STREAM_LEVEL = logging.DEBUG
_FILE_LEVEL = logging.DEBUG

# logging.getLogger().setLevel(logging.DEBUG)


class RichFormatter(logging.Formatter):
    """Custom formatter that uses Rich for colorized output."""

    def __init__(self, console: Console | None = None, emoji: str = ""):
        super().__init__()
        self.console = console or Console()
        self.emoji = emoji + " " if emoji and not emoji.endswith(" ") else emoji
        self.level_colors = {
            logging.DEBUG: "dim cyan",
            logging.INFO: "green",
            logging.WARNING: "yellow",
            logging.ERROR: "red",
            logging.CRITICAL: "bold red",
        }

    def format(self, record: logging.LogRecord) -> str:
        level_color = self.level_colors.get(record.levelno, "white")
        level_name = record.levelname.replace("WARNING", "WARN")

        # Calculate the prefix length for indentation
        prefix = f"{self.emoji}{level_name} [{record.name}] "
        indent = " " * len(prefix)

        text = Text()
        text.append(self.emoji, style="white")
        text.append(f"{level_name} ", style=level_color)
        text.append(f"[{record.name}] ", style="dim")

        # Handle multiline messages by indenting continuation lines
        message = record.getMessage()
        lines = message.split("\n")
        text.append(lines[0], style="white")

        for line in lines[1:]:
            text.append("\n")
            text.append(indent, style="dim")
            text.append(line, style="white")

        if record.exc_info:
            text.append("\n")
            exception_lines = self.formatException(record.exc_info).split("\n")
            for i, exc_line in enumerate(exception_lines):
                if i > 0:
                    text.append("\n")
                    text.append(indent, style="dim")
                text.append(exc_line, style="red")

        with self.console.capture() as capture:
            self.console.print(text)
        return capture.get().rstrip()


def add_file_handler(logger: logging.Logger, log_path: Path) -> logging.FileHandler:
    """Add a file handler to the logger with standard formatting.

    Returns:
        The FileHandler that was added (for later cleanup).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(_FILE_LEVEL)

    # Use a standard formatter for file logs with time, name, and level
    file_formatter = logging.Formatter(
        fmt="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    logger.addHandler(file_handler)
    return file_handler


def add_root_file_handler(log_path: Path) -> logging.FileHandler:
    """Add a file handler to the root logger to capture all log messages.

    Returns:
        The FileHandler that was added (for later cleanup).
    """
    return add_file_handler(logging.getLogger(), log_path)


def remove_file_handler(logger: logging.Logger, handler: logging.FileHandler) -> None:
    """Remove and close a file handler from the logger."""
    if handler in logger.handlers:
        logger.removeHandler(handler)
    handler.close()


def get_logger(name: str, *, emoji: str = "", log_path: Path | None = None) -> logging.Logger:
    """Get logger. Use this instead of `logging.getLogger` to ensure
    that the logger is set up with the correct handlers.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        # Already set up
        return logger

    console = Console()
    handler = logging.StreamHandler()
    formatter = RichFormatter(console, emoji=emoji)

    handler.setFormatter(formatter)
    handler.setLevel(_STREAM_LEVEL)

    # Set to lowest level and only use stream handlers to adjust levels
    logger.setLevel(1)
    logger.addHandler(handler)
    logger.propagate = True

    if log_path is not None:
        add_file_handler(logger, log_path)

    return logger
