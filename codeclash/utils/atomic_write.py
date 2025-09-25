from pathlib import Path


def atomic_write(path: Path, text: str) -> None:
    """Write text to file atomically to prevent corruption on interruption."""
    tmp_file = path.with_suffix(".tmp")
    tmp_file.write_text(text)
    tmp_file.rename(path)
