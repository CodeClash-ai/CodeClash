__version__ = "0.0.0"

# Optional viewer import - only if Flask dependencies are available
from pathlib import Path

try:
    from . import viewer  # noqa: F401
except ImportError:
    pass


CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"
